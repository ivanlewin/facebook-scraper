import json
import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from configparser import ConfigParser
from datetime import datetime
from pandas.errors import EmptyDataError
from re import match, search
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

            url_dict = analyze_url(post)

            driver = get_mobile_post(driver, post)
            post_df = bs4_parse(driver.page_source)

            if comments:
                print("Scraping comments")
                comments_df = scrape_comments(driver, replies=replies)

                try:
                    post_df = pd.concat([post_df] * len(comments_df.index))  # Repeat the post_df rows to match the comments count
                    post_df = pd.concat([post_df, comments_df], axis=1)  # Join the two dataframes together, side to side horizontally

                except ValueError:  # Empty df
                    pass

            if reactions:
                pass

            save_dataframe(post_df, dest_path)
            print(f"Database saved: {dest_path}\n")

    driver.quit()


def read_config():

    config = ConfigParser()
    config.read('./scripts/config.txt')

    comments = config.getboolean("comments", "scrape_comments")
    replies = config.getboolean("comments", "scrape_replies")
    custom_folder = config.get("output", "output_folder")

    settings = {
        "comments": comments,
        "replies": replies,
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
    pass


def bs4_parse(html):

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

    comments_enabled = post_json.get("comments_disabled")
    if comments_enabled != None : post_is_comment_enabled = not(comments_enabled)
    
    like_count = post_json.get("edge_media_preview_like").get("count")
    if like_count: post_like_count = int(like_count)
    post_shortcode = post_json.get("shortcode")
    try:
        owner = soup.select('#u_0_z')[0]
        owner = json.loads(owner['data-store'])

        if owner:
            post_id = re.search(r'mf_story_key.(\d+)', owner['linkdata'])[1]
            post_owner = re.search(r'content_owner_id_new.(\d+)', owner['linkdata'])[1]

            timestamp = re.search(r'"publish_time":(\d+)', owner['linkdata'])[1]
            post_timestamp = datetime.fromtimestamp(int(timestamp))

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
    post_df["p_ig_id"] = [post_ig_id]
    post_df["p_is_comment_enabled"] = [post_is_comment_enabled]
    post_df["p_like_count"] = [post_like_count]
    post_df["p_media_type"] = [post_media_type]
    # post_df["p_media_url"] = [post_media_url]
    post_df["p_owner"] = [post_owner]
    # post_df["p_permalink"] = [post_permalink]
    post_df["p_shortcode"] = [post_shortcode]
    post_df["p_timestamp"] = [post_timestamp]
    post_df["p_username"] = [post_username]
    post_df["p_views_count"] = [post_views_count]
    post_df["p_location"] = [post_location]
    post_df["p_location_id"] = [post_location_id]

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


def scrape_comments(driver, replies=False):

    def load_comments():
        """Clicks the "Load more comments" button until there are no more comments."""
        while True:
            try:
                load_more_comments = driver.find_element_by_css_selector("button.dCJp8")
                load_more_comments.click()
                sleep(2)
            except NoSuchElementException:
                break

    def load_replies():
        try:
            view_replies_buttons = driver.find_elements_by_css_selector(".y3zKF")

            for button in view_replies_buttons:

                try:
                    driver.execute_script("arguments[0].scrollIntoView();", button)

                    text = button.text
                    while "Ver" in text or "View" in text:
                        button.click()
                        sleep(0.5)
                        text = button.text

                except (StaleElementReferenceException, ElementClickInterceptedException):
                    pass

        except (NoSuchElementException):
            pass

    def get_comment_info(comment):

        comment_id = comment_reply_id = comment_timestamp = comment_username = comment_text = comment_like_count = None

        try:
            comment_username = comment.find_element_by_css_selector("h3 a").text
            comment_text = comment.find_element_by_css_selector("span:not([class*='coreSpriteVerifiedBadgeSmall'])").text

            info = comment.find_element_by_css_selector(".aGBdT > div")

            permalink = info.find_element_by_css_selector("a")
            m = match(r"(?:https:\/\/www\.instagram\.com\/p\/.+)\/c\/(\d+)(?:\/)(?:r\/(\d+)\/)?", permalink.get_attribute("href"))
            comment_id = m[1]
            comment_reply_id = m[2]

            comment_timestamp = info.find_element_by_tag_name("time").get_attribute("datetime")
            comment_timestamp = datetime.strptime(comment_timestamp, r"%Y-%m-%dT%H:%M:%S.%fZ")
            # comment_timestamp = datetime.timestamp(comment_timestamp)

            likes = info.find_element_by_css_selector("button.FH9sR").text
            m = match(r"(\d+)", likes)
            if m:
                comment_like_count = int(m[0])
            else:
                comment_like_count = 0

        except NoSuchElementException:
            pass

        comment_df = pd.DataFrame({
            "c_username": [comment_username],
            "c_timestamp": [comment_timestamp],
            "c_text": [comment_text],
            "c_like_count": [comment_like_count],
            "c_id": [comment_id],
            "c_reply_id": [comment_reply_id],
        })

        comment_df = comment_df.astype({"c_id": object, "c_reply_id": object})

        return comment_df

    comments_df = pd.DataFrame()

    load_comments()
    if replies:
        load_replies()

    try:
        for comment in driver.find_elements_by_css_selector("ul.XQXOT > ul.Mr508 div.ZyFrc div.C4VMK"):
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

    # use output_folder if it's not None, else default folder
    folder = os.path.abspath(output_folder) if output_folder else os.path.abspath("./csv")

    if not os.path.exists(folder):
        os.mkdir(folder)

    filename = f"{prefix}_{timestamp}.csv"

    return os.path.join(folder, filename)


if __name__ == "__main__":
    config = read_config()
    # main(**config)

post_mobile = 'https://m.facebook.com/DonaldTrump/posts/10165125042920725'
post_desktop = 'https://www.facebook.com/DonaldTrump/posts/10165125042920725'
reactions_mobile = 'https://m.facebook.com/ufi/reaction/profile/browser/?ft_ent_identifier=10165125042920725'

r_post_mobile = requests.get(post_mobile)
r_post_desktop = requests.get(post_desktop)
r_reactions_mobile = requests.get(reactions_mobile)  # No sirve

with open("response_post_mobile.html", "w", encoding="utf-8") as f:
    f.write(r_post_mobile.text)
with open("response_post_desktop.html", "w", encoding="utf-8") as f:
    f.write(r_post_desktop.text)
with open("response_reactions_mobile.html", "w", encoding="utf-8") as f:
    f.write(r_reactions_mobile.text)

driver.get(post_mobile)
driver.get(post_desktop)
driver.get(reactions_mobile)
with open("page_source_reactions_mobile.html", "w", encoding="utf-8") as f:
    f.write(driver.page_source)