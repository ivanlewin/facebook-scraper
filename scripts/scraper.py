import json
import os
import pandas as pd
import re
from bs4 import BeautifulSoup
from configparser import ConfigParser
from datetime import datetime
from pandas.errors import EmptyDataError
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from time import sleep


def main(**kwargs):

    comments = kwargs.get("comments")
    replies = kwargs.get("replies")
    output_folder = kwargs.get("custom_folder")

    post_dict = read_posts()

    driver = load_driver(driver="Chrome", existing_profile=True)

    for user in post_dict:

        dest_path = get_file_path(user, output_folder)

        for post in post_dict[user]:
            print(f"User: {user} | Post {post_dict[user].index(post)+1}/{len(post_dict[user])}")

            # url_dict = analyze_url(post)

            driver.get(post)
            get_mobile_post(driver)
            post_df = parse_post(driver.page_source)

            if comments:
                print("Loading comments")
                load_all_comments(driver)

                if replies:
                    print("Loading replies")
                    load_all_replies(driver)

                comments_df = scrape_comments(driver.page_source)

                try:
                    # unir las df, añadiendo la informacion del posteo a cada comment
                    post_df = pd.concat([post_df] * len(comments_df.index))
                    post_df = pd.concat([post_df, comments_df], axis=1)

                except ValueError:  # Empty df
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


def get_mobile_post(driver):
    
    # urls de posteos scrapeables
    target_urls = [re.compile(r"facebook\.com\/(?:(?P<profile_id>\d+)|(?P<profile_name>[a-zA-Z0-9.]+))\/(?:posts)\/(?P<post_id>\d+)"),
                   re.compile(r"facebook\.com\/story\.php\?((?:story_fbid=(?P<post_id>\d+)))&((?:id=(?:(?P<profile_id>\d+))))"),
                   re.compile(r"facebook\.com\/photo\.php\?(?:(?:fbid=(?P<post_id>\d+)))&(?:(?:id=(?:(?P<profile_id>\d+)|(?P<profile_name>[a-zA-Z0-9.]+))))&(?:(?:set=a\.(?P<album_id>\d+)))")]

    # si la url matchea con algún patron
    if any([re.search(pattern, driver.current_url) for pattern in target_urls]):
        return

    if "www.facebook.com" in driver.current_url:
        driver.get(driver.current_url.replace("www.facebook.com", "m.facebook.com"))

    try:
        parent_post = driver.find_element_by_css_selector('div._2vja')
        for link in parent_post.find_elements_by_css_selector("a"):
            url = link.get_attribute("href")
            if any([re.search(target_url, url) for target_url in target_urls]):
                #  hay que hacer driver.get() en lugar de link.click() para que cargue toda
                # la página desde 0 y no quede información del link anterior (que no se puede scrapear)
                driver.get(url)
                return

    except NoSuchElementException:
        pass

    try:
        parent_post = driver.find_element_by_css_selector("div#mobile_injected_video_feed_pagelet ._52jc > a")
        driver.get(parent_post.get_attribute("href"))

    except NoSuchElementException:
        pass

    return get_mobile_post(driver)


def parse_post(html):

    # Inicializo las columnas en None
    post_comments_count = post_shares_count = post_caption = post_id = post_reactions_count = post_author_id = post_created_time = post_author = None

    soup = BeautifulSoup(html, "html.parser")

    try:
        post_caption = soup.select_one('._5rgt._5nk5').text
    except AttributeError:  # No caption
        print("Error: post_caption")

    try:
        shares = soup.select_one('div._43lx._55wr a')
        shares = re.search(r'(\d+)', shares.string)[0]
        post_shares_count = int(shares)
    except (IndexError, TypeError, AttributeError):
        print("Error: post_shares_count")

    try:
        username = soup.select_one('div._4g34._5i2i._52we h3 a')
        post_author = username.string
    except (IndexError, TypeError, AttributeError):
        print("Error: post_author")

    try:
        owner = soup.select_one('div._5rgr')
        owner = json.loads(owner['data-store'])

        if owner:
            post_id = re.search(r'mf_story_key.(\d+)', owner['linkdata'])[1]
            post_author_id = re.search(r'content_owner_id_new.(\d+)', owner['linkdata'])[1]

            timestamp = re.search(r'"publish_time":(\d+)', owner['linkdata'])[1]
            post_created_time = datetime.fromtimestamp(int(timestamp))

    except (IndexError, TypeError, KeyError):
        print("Error: post_id | post_author_id | post_created_time")

    # busco un json con metricas en el page_source de la pagina
    unparsed_json = None
    json_inicio = f"{{ft_ent_identifier:{post_id}"
    json_final = ",reactorids"

    if json_inicio in html:
        unparsed_json = html[html.index(json_inicio):html.index(json_final)]  # substring del json 'minificado'

    else:
        # el post_id puede que este entre comillas
        json_inicio = f"{{ft_ent_identifier:\"{post_id}\""
        if json_inicio in html:
            unparsed_json = html[html.index(json_inicio):html.index(json_final)]  # substring del json 'minificado'

    if unparsed_json is not None:
        parsed_json = re.sub(r'(\w+):', r'"\1":', unparsed_json) # agrego quotes a las keys del json, y agrego un '}' al final
        post_metricas = json.loads(parsed_json)  # parseo el string como un diccionario

        post_comments_count = post_metricas["comment_count"]
        post_reactions_count = post_metricas["reactioncount"]

        print("Error: post_comments_count | post_reactions_count")

    post_df = pd.DataFrame({
        "p_comments_count": [post_comments_count],
        "p_caption": [post_caption],
        "p_id": [post_id],
        "p_reactions_count": [post_reactions_count],
        "p_shares_count": [post_shares_count],
        # "p_media_url": [post_media_url],
        "p_author_id": [post_author_id],
        # # "p_permalink_url": [post_permalink_url],
        "p_created_time": [post_created_time],
        "p_author": [post_author],
    })

    # cambio el datatype de las columnas de id a strings para que no los castee a numbers
    post_df = post_df.astype({"p_id": object, "p_author_id": object})

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
    """
    Clickea el boton de "View more comments" hasta que no encuentre nuevos comments.

    El boton no desaparece cuando ya no hay comentarios; sigue funcionando pero no hace nada.
    Por eso se chequea el último comentario y se lo compara cada vez que se aprieta el botón
    """

    last_comment = None

    while True:

        try:
            # boton al final de todo
            view_more_comments = driver.find_element_by_css_selector("div[id*='see_next_']")
            # hacer scroll hasta que este enfocado y clickearlo
            driver.execute_script("arguments[0].scrollIntoView();", view_more_comments)
            view_more_comments.click()
            sleep(2)

            # scrollear hasta el boton
            view_more_comments = driver.find_element_by_css_selector("div[id*='see_next_']")
            driver.execute_script("arguments[0].scrollIntoView();", view_more_comments)

            # chequear el comentario inmediatamente anterior al boton para ver si cambio
            preceding_comment = view_more_comments.find_element_by_xpath("./preceding-sibling::*[1][@class='_2a_i']")

            if preceding_comment == last_comment:
                break
            else:
                last_comment = preceding_comment
            
        except NoSuchElementException:  # no hay botón de ver más (muy pocos comentarios)
            break


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


def scrape_comments(html):

    comments_df = pd.DataFrame()
    soup = BeautifulSoup(html, "html.parser")

    for comment in soup.select("._333v._45kb > ._2a_i"):  # top-level comments o threads (comentarios con replies)

        if "_2a_l" not in comment["class"]:  # los threads tienen esta clase -> este comentario no tiene replies
            try:
                comment_df = get_comment_info(comment, parent=None, reply_count=0)
            except ValueError:  # df vacio
                pass

        else:  # hay replies
            replies = comment.select("._2a_m ._2a_i")
            comment_df = get_comment_info(comment, parent=None, reply_count=len(replies))
            thread_id = comment["id"]  # uso el comment_id de este comentario como parent_id de las replies
            for reply in replies:
                try:
                    reply_df = get_comment_info(reply, parent=thread_id, reply_count=0)
                    comment_df = pd.concat([comment_df, reply_df])
                except ValueError:  # df vacio
                    pass

        comments_df = pd.concat([comments_df, comment_df])

    return comments_df


def get_comment_info(comment, parent, reply_count):

    # Inicializo las columnas en None
    comment_id = comment_author = comment_author_name = comment_reactions_count = comment_message = None

    comment_id = comment["id"]  # atributo id del div

    author = comment.select_one("._2b05 > a")
    m = re.match(r'(?:\/(profile\.php\?id=)?)(\d+|[^\?\&]*)', author['href'])  # matchea el id o el username, en ese orden
    comment_author = m[2]
    comment_author_name = author.text

    message = comment.select_one("div[data-commentid]")
    # cuando no hay mensaje (por ej, cuando el comentario es un sticker), hay un solo div con
    # clase _2b05 y el atributo data-commentid (en vez de dos divs separados). el textContent de ese elemento
    # es comment_author_name, pero deberia ser None (o un string vacio).

    if message.get("class") is not None:
        if "_2b05" in message["class"]:
            comment_message = None
    else:
        comment_message = message.text

    reactions = comment.select_one('span._14va').text
    # asigno las reactions a la columna, si tiene, o reemplazo el string vacío del span por un 0
    comment_reactions_count = reactions if reactions != "" else 0

    comment_df = pd.DataFrame({
        "c_author_name": [comment_author_name],
        "c_author": [comment_author],
        "c_message": [comment_message],
        "c_reactions_count": [comment_reactions_count],
        "c_reply_count": [reply_count],
        "c_id": [comment_id],
        "c_parent": [parent]  # se pasa como parametro de la funcion
    })

    # cambio el datatype de las columnas de id a strings para que no los castee a numbers
    comment_df = comment_df.astype({"c_id": object, "c_parent": object, "c_author": object})

    return comment_df


def save_dataframe(df, path):

    try:
        base_df = pd.read_csv(path)
        new_df = pd.concat([base_df, df])
        new_df.to_csv(path, index=False)

    except (FileNotFoundError, EmptyDataError):
        df.to_csv(path, index=False)


def get_file_path(prefix, output_folder, timestamp=datetime.now().strftime(r"%Y%m%d")):

    # usar la output_folder si la hay, o la carpeta "/csv" por defecto
    if output_folder is not None:
        folder = os.path.abspath(output_folder)
    else:
        folder = os.path.abspath("./csv")

    if not os.path.exists(folder):
        os.mkdir(folder)

    filename = f"{prefix}_{timestamp}.csv"

    return os.path.join(folder, filename)


if __name__ == "__main__":
    config = read_config()
    main(**config)

# with open("page_source_mobile_chrome_all_comments.html", "r", encoding='utf-8') as f:
#     html = f.read()

# post_df = parse_post(html)
# comments_df = scrape_comments(html)
# post_df = pd.concat([post_df] * len(comments_df.index))
# post_df = pd.concat([post_df, comments_df], axis=1)
# save_dataframe(post_df, dest_path)
