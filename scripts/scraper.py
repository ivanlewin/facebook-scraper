import json
import os
import pandas as pd
import re
from bs4 import BeautifulSoup
from configparser import ConfigParser
from datetime import datetime
from pandas.errors import EmptyDataError
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException
from time import sleep


def main(**kwargs):

    # read kwargs arguments
    comments = kwargs.get("comments")
    replies = kwargs.get("replies")
    reactions = kwargs.get("reactions")
    output_folder = kwargs.get("custom_folder")

    post_dict = read_posts()

    driver = load_driver(driver="Chrome", existing_profile=True)

    for user in post_dict:

        dest_path = get_file_path(user, output_folder)

        for post in post_dict[user]:
            print(f"User: {user} | Post {post_dict[user].index(post)+1}/{len(post_dict[user])}")

            # url_dict = analyze_url(post)

            driver = get_mobile_post(driver, post)

            if comments:
                print("Loading comments")
                load_all_comments(driver)

                if replies:
                    print("Loading replies")
                    load_all_replies()

                comments_df = scrape_comments(driver, replies=replies)

                try:
                    post_df = pd.concat([post_df] * len(comments_df.index))  # Repeat the post_df rows to match the comments count
                    post_df = pd.concat([post_df, comments_df], axis=1)  # Join the two dataframes together, side to side horizontally

                except ValueError:  # Empty df
                    pass

            if reactions:
                pass

            post_df = parse_post(driver.page_source)
            save_dataframe(post_df, dest_path)
            print(f"Database saved: {dest_path}\n")

    driver.quit()


def read_config():

    config = ConfigParser()
    config.read('./scripts/config.txt')

    comments = config.getboolean("comments", "scrape_comments")
    replies = config.getboolean("comments", "scrape_replies")
    reactions = config.getboolean("comments", "scrape_reactions")

    custom_folder = config.get("output", "output_folder")

    settings = {
        "comments": comments,
        "replies": replies,
        "reactions": reactions,
        "custom_folder":  custom_folder if custom_folder else None,
    }

    return settings


def read_posts():
    posts = {}
    folder = "./posts"
    for file in os.listdir(folder)[1:]:  # Ignore the .gitkeep file
        user, _ = os.path.splitext(file)
        if user:
            with open(os.path.join(folder, file), "r") as f:
                posts[user] = [p for p in f.read().splitlines()]

    return posts


def analyze_url(url):
    """Analizar la url y ver qué información \
    se puede extraer acerca del posteo"""

    profile_id = profile_name = post_id = photo_id = video_id = album_id = None

    regex_posts = re.compile(r"facebook\.com\/(?:(?P<profile_id>\d+)|(?P<profile_name>[a-zA-Z0-9.]+))\/(?:posts)\/(?P<post_id>\d+)")
    regex_story_php = re.compile(r"facebook\.com\/story\.php\?((?:story_fbid=(?P<post_id>\d+)))&((?:id=(?:(?P<profile_id>\d+))))")
    regex_photo_php = re.compile(r"facebook\.com\/photo\.php\?(?:(?:fbid=(?P<post_id>\d+)))&(?:(?:id=(?:(?P<profile_id>\d+)|(?P<profile_name>[a-zA-Z0-9.]+))))&(?:(?:set=a\.(?P<album_id>\d+)))")
    regex_videos = re.compile(r"facebook\.com\/(?:(?P<profile_id>\d+)|(?P<profile_name>[a-zA-Z0-9.]+))\/videos\/(?P<video_id>\d+)")
    regex_videos_watch = re.compile(r"facebook\.com\/watch\/(?:live\/)?\?((?:v=(?P<video_id>\d+)))")
    regex_photo_posts = re.compile(r"facebook\.com\/(?:(?P<profile_id>\d+)|(?P<profile_namme>[a-zA-Z0-9.]+))\/(?:photos)\/(?:(?:pcb\.(?P<post_id>\d+)))\/(?:(?P<photo_id>\d+))")

    # patterns = [regex_posts, regex_story_php, regex_photo_php, regex_videos,
    #     regex_videos_watch, regex_photo_posts]
    
    # for pattern in patterns:
        # if re.match()

    m = re.search(regex_posts, url)
    if m.groupdict() is not None:
        post_id = m_dict.get("post_id")
        profile_name = m_dict.get("profile_name")
        profile_id = m_dict.get("profile_id")

    
    if (m := re.match(regex_posts, url)):
        m_dict = m.groupdict()

        post_id = m_dict.get("post_id")
        profile_name = m_dict.get("profile_name")
        profile_id = m_dict.get("profile_id")

    elif (m := re.match(regex_story_php, url)):
        pass

    reactions_url = f'https://m.facebook.com/ufi/reaction/profile/browser/?ft_ent_identifier={post_id}'


def get_mobile_post(driver, url):
    driver.get(url.replace("www.facebook.com", "m.facebook.com"))
    return driver


def parse_post(html):

    # Initialize dataframe instance, and set post metadata to None
    post_df = pd.DataFrame()
    post_comments_count = post_shares_count = post_caption = post_id = post_is_comment_enabled = post_like_count = post_media_type = post_owner = post_shortcode = post_timestamp = post_username = post_views_count = post_location = post_location_id = None

    soup = BeautifulSoup(html, "html.parser")

    # Search for a script that contains the post metadata
    for script in soup.select("script[type='text/javascript']"):
        if (script.string and script.string.startswith("window._sharedData")):
            json_string = script.string.replace("window._sharedData = ", "")[:-1]
            post_info = json.loads(json_string)
    
    try:
        post_json = post_info["entry_data"]["PostPage"][0]["graphql"]["shortcode_media"]
    except KeyError: # Possibly a private post 
        post_json = post_info["entry_data"]["ProfilePage"][0]["graphql"]["user"]

    comments_count = post_json.get("edge_media_to_parent_comment").get("count")
    if comments_count : post_comments_count = int(comments_count)

    try:
        post_caption = soup.select('._5rgt._5nk5')[0].text
    except (IndexError, TypeError):  # No caption
        pass

    try:
        shares = soup.select('div._43lx._55wr a')[0]
        shares = re.search(r'(\d+)', shares.string)[0]
        post_shares_count = int(shares)
    except (IndexError, TypeError):
        print("Error: post_shares_count")

    # like_count = post_json.get("edge_media_preview_like").get("count")
    # if like_count:
    #     post_like_count = int(like_count)

    try:
        username = soup.select('div._4g34._5i2i._52we h3 a')[0]
        post_author = username.string
    except (IndexError, TypeError):
        print("Error: post_author")

    try:
        owner = soup.select('#u_0_z')[0]
        owner = json.loads(owner['data-store'])

        if owner:
            post_id = re.search(r'mf_story_key.(\d+)', owner['linkdata'])[1]
            post_owner = re.search(r'content_owner_id_new.(\d+)', owner['linkdata'])[1]

            timestamp = re.search(r'"publish_time":(\d+)', owner['linkdata'])[1]
            post_timestamp = datetime.fromtimestamp(int(timestamp))

            # selector para post_timestamp con request del posteo version desktop
            # a._5pcq > abbr[data-utime]

    except (IndexError, TypeError):
        print("Error: post_id, post_owner, post_timestamp")

    media_type = post_json.get("__typename")
    if media_type == "GraphImage":
        post_media_type = "IMAGE"
    elif media_type == "GraphSidecar":
        post_media_type = "CAROUSEL_ALBUM"
    elif media_type == "GraphVideo":
        post_media_type = "VIDEO"

    post_views_count = post_json.get("video_view_count")
    
    # Fill dataframe with values, which will be None if not found
    post_df["p_comments_count"] = [post_comments_count]
    post_df["p_caption"] = [post_caption]
    # post_df["p_id"] = [post_id]
    post_df["p_id"] = [post_id]
    post_df["p_like_count"] = [post_like_count]
    post_df["p_shares_count"] = [post_shares_count]
    # post_df["p_media_url"] = [post_media_url]
    post_df["p_owner"] = [post_owner]
    # post_df["p_permalink"] = [post_permalink]
    post_df["p_timestamp"] = [post_timestamp]
    post_df["p_username"] = [post_username]
    post_df["p_views_count"] = [post_views_count]

    post_df = post_df.astype({"p_ig_id": object, "p_owner": object, "p_location_id": object})

    return post_df


def load_driver(driver="Firefox", existing_profile=False, profile=None):
    """Loads and returns a webdriver instance.

    Keyword arguments:
    driver -- which driver you want to use
        "Chrome" for chromedriver or "Firefox" for geckodriver.
    existing_profile -- wether you want to use an existing browser profile,
        which grants access to cookies and other session data.
    profile -- the path to the profile you want to use.
        By default it will look into the default profiles_folder for the selected browser
        and choose the first one, but it may be the case that you want to use another one.
    """
    if driver == "Firefox":

        if existing_profile:

            if not profile:
                profiles_folder = os.path.expandvars("%APPDATA%\\Mozilla\\Firefox\\Profiles")
                profile = os.path.join(profiles_folder, os.listdir(profiles_folder)[1])  # Selecting first profile in the folder

            firefox_profile = webdriver.FirefoxProfile(profile_directory=profile)
            driver = webdriver.Firefox(firefox_profile)

        else:
            driver = webdriver.Firefox()

    if driver == "Chrome":

        if existing_profile:

            if not profile:
                profile = os.path.expandvars("%LOCALAPPDATA%\\Google\\Chrome\\User Data")  # Selects Default profile

            options = webdriver.ChromeOptions()
            options.add_argument("user-data-dir=" + profile)
            driver = webdriver.Chrome(chrome_options=options)

        else:
            driver = webdriver.Chrome()

    return driver


def load_all_comments(driver):
    """Clickea el boton de "View more comments" hasta que no encuentre nuevos comments."""
    last_comment = None
    while True:
        # boton al final de todo
        view_more_comments = driver.find_element_by_css_selector("div[id*='see_next_']")
        # hacer scroll hasta que este enfocado y clickearlo
        driver.execute_script("arguments[0].scrollIntoView();", view_more_comments)
        view_more_comments.click()
        sleep(2)

        # el boton no desaparece cuando ya no hay comentarios; sigue funcionando pero no hace nada
        
        # scrollear hasta el boton
        view_more_comments = driver.find_element_by_css_selector("div[id*='see_next_']")
        driver.execute_script("arguments[0].scrollIntoView();", view_more_comments)

        # chequear el comentario inmediatamente anterior al boton para ver si cambio
        preceding_comment = view_more_comments.find_element_by_xpath("./preceding-sibling::*[1][@class='_2a_i']")

        # chequear que el ultimo comment no sea igual al ultimo guardado
        if preceding_comment == last_comment:
            break
        else:
            last_comment = preceding_comment


def load_all_replies(driver):
    """Clickea todos los botones de 'x reply(ies)' hasta que no encuentre ninguno."""
    while True:
        try:
            view_replies_buttons = driver.find_element_by_css_selector("div[id*='comment_replies_more_']")
            driver.execute_script("arguments[0].scrollIntoView();", view_replies_buttons)
            view_replies_buttons.click()
            sleep(2)
        except (NoSuchElementException):
            break


def get_comment_info(comment):

    comment_id = comment_reply_count = comment_created_time = comment_from = comment_like_count = comment_message = comment_parent = None

    try:
        comment_from = comment.find_element_by_css_selector("h3 a").text
        comment_message = comment.find_element_by_css_selector("div[data-commentid]").text

        info = comment.find_element_by_css_selector(".aGBdT > div")

        permalink = info.find_element_by_css_selector("a")
        m = re.match(r"(?:https:\/\/www\.instagram\.com\/p\/.+)\/c\/(\d+)(?:\/)(?:r\/(\d+)\/)?", permalink.get_attribute("href"))
        comment_id = m[1]
        comment_parent = m[2]

        comment_created_time = info.find_element_by_tag_name("time").get_attribute("datetime")
        comment_created_time = datetime.strptime(comment_created_time, r"%Y-%m-%dT%H:%M:%S.%fZ")

        likes = info.find_element_by_css_selector("button.FH9sR").text
        m = re.match(r"(\d+)", likes)
        if m:
            comment_like_count = int(m[0])
        else:
            comment_like_count = 0

    except NoSuchElementException:
        pass

    comment_df = pd.DataFrame({
        "c_from": [comment_from],
        "c_created_time": [comment_created_time],
        "c_message": [comment_message],
        "c_like_count": [comment_like_count],
        "c_reply_count": [comment_reply_count],
        "c_id": [comment_id],
        "c_parent": [comment_parent],
    })

    comment_df = comment_df.astype({"c_id": object, "c_reply_id": object})

    return comment_df


def scrape_comments(driver, replies=False):

    comments_df = pd.DataFrame()

    load_all_comments()
    if replies:
        load_all_replies()

    try:
        for comment in soup.select("._2a_i ._14v5"):
            driver.execute_script("arguments[0].scrollIntoView();", comment)
            comment_df = get_comment_info(comment)
            comments_df = pd.concat([comments_df, comment_df])

    except ValueError:  # empty df
        pass

    return comments_df


def save_dataframe(df, path):

    try:
        base_df = pd.read_csv(path)
        new_df = pd.concat([base_df, df])
        new_df.to_csv(path, index=False)

    except (FileNotFoundError, EmptyDataError):
        df.to_csv(path, index=False)


def get_file_path(prefix, output_folder, timestamp=datetime.now().strftime(r"%Y%m%d")):

    # use custom output_folder if there's one, else default folder
    if output_folder:
        folder = os.path.abspath(output_folder)
    else:
        folder = os.path.abspath("./csv")

    if not os.path.exists(folder):
        os.mkdir(folder)

    filename = f"{prefix}_{timestamp}.csv"

    return os.path.join(folder, filename)


if __name__ == "__main__":
    config = read_config()
    # main(**config)