#!/usr/bin/env python3
"""
This is an experiment to take libsyn's RSS feed and generate markdown files
for a github pages website.
"""

import argparse
import feedparser
import csv
import time
import os
import requests
import urllib
import git
import ssl
from bs4 import BeautifulSoup

FEED_URL = "http://reverseengineering.libsyn.com/rss"
IMG_DIR = "images"
DIR_ID_FILENAME = "_sitegen/directory_ids.csv"


dir_ids = {}

# List of 'useless' html that I don't want with the string that replaces it
strip_strings = [
    ('<span style="font-weight: 400;">', ""),
    ("</span>", ""),
    (' style="font-weight: 400;"', ""),
]


def strip_unwanted_tags(html, repo_path):
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove all span tags by unwrapping them (keeps the content)
    for span in soup.find_all("span"):
        span.unwrap()
    
    # Remove all style and dir attributes from all elements
    for element in soup.find_all(True):  # find_all(True) finds all tags
        if element.has_attr('style'):
            del element['style']
        if element.has_attr('dir'):
            del element['dir']
    
    # Also handle the other unwanted strings
    html = str(soup)
    for old_string, new_string in strip_strings:
        html = html.replace(old_string, new_string)

    return html


def get_img_str(src, title=None, caption=None, url=None):
    img_str = "{% include image.html "
    img_str += 'img="{}" '.format(src)

    if title:
        img_str += 'title="{}" '.format(title)
    if caption:
        img_str += 'caption="{}" '.format(caption)
    if url:
        img_str += 'url="{}" '.format(url)
    img_str += "%}"

    return img_str


def download_and_replace_images(html, repo_path):
    """ No need to keep using the libsyn hosted images. Download and
        use a local copy instead """

    # Make sure we have an image directory!
    img_path = os.path.join(repo_path, IMG_DIR)
    os.makedirs(img_path, exist_ok=True)

    soup = BeautifulSoup(html, "html.parser")
    for img in soup.find_all("img"):
        src = img["src"]
        img_filename = os.path.basename(urllib.parse.urlparse(src).path)
        new_img_path = os.path.join(img_path, img_filename)

        if not os.path.isfile(new_img_path):
            print("Downloading ", src)
            request = requests.get(src)
            if request is not None:
                with open(new_img_path, "wb") as image:
                    image.write(request.content)

        if img.parent.name == "a":
            href = img.parent.get("href")
            parent = img.parent.parent
            del img.parent
        else:
            href = None
            parent = img.parent
            del img

        img_src = new_img_path.replace(repo_path, "")

        if href is None:
            href = img_src

        parent.string = get_img_str(img_src, url=href)

    html = soup.prettify()

    return html


# Ordered list of processing function to be run on html
processing_functions = [strip_unwanted_tags, download_and_replace_images]


def process_html(html, repo_path):
    """ Go through each processing function, in order """

    for fn in processing_functions:
        # Make sure each function gets 'pretty' html
        soup = BeautifulSoup(html, "html.parser")
        html = fn(soup.prettify(), repo_path)

    # Do one last prettifying before finishing
    soup = BeautifulSoup(html, "html.parser")
    html = soup.prettify()

    return html


def load_dir_ids(filename):
    with open(filename) as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            # Todo, check for valid data
            dir_ids[int(row[0])] = int(row[1])


def get_dir_id(entry):
    try:
        episode_num = int(entry.title.split(" - ")[0])
        return dir_ids.get(episode_num)
    except ValueError:
        return None


def post_header(entry):
    header = []
    header.append("---")
    header.append("layout: episode")
    header.append('title: "' + entry.title + '"')
    
    # Get subtitle, prompt user if missing
    subtitle = getattr(entry, 'subtitle', None)
    if subtitle is None:
        subtitle = input(f'Enter subtitle for "{entry.title}": ')
    
    header.append('subtitle: "{}"'.format(subtitle.replace('"','\\"')))
    header.append(time.strftime("date: %Y-%m-%d %H:%M:%S", entry.published_parsed))
    header.append("categories: episode")
    header.append("dir_id: " + str(get_dir_id(entry)))
    header.append("permalink: episode/{}".format(int(entry.title.split(" - ")[0])))
    header.append("---\n")

    return "\n".join(header)


def generate_filename(entry):

    date_str = time.strftime("%Y-%m-%d", entry.published_parsed)

    title = entry.title.replace(" ", "_")

    # Remove non alphanumeric characters (keep _ and -)
    title = "".join(x for x in title if x.isalnum() or x in "_-")

    return date_str + "-" + title + ".md"


parser = argparse.ArgumentParser()

print("Starting to process feed at ", FEED_URL)
parser.add_argument(
    "--overwrite", action="store_true", help="Overvwrite existing markdown files"
)
args = parser.parse_args()
git_repo = git.Repo(".", search_parent_directories=True)
repo_path = git_repo.git.rev_parse("--show-toplevel")
print("Loading Posts directory")
load_dir_ids(DIR_ID_FILENAME)

# Workaround for failed cert issue from:
# https://stackoverflow.com/questions/28282797/feedparser-parse-ssl-certificate-verify-failed
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context
print("Load remote feed URL.")
d = feedparser.parse(FEED_URL)
print("Process entries:")
for entry in d.entries:
    filename = generate_filename(entry)
    posts_path = repo_path + "/_posts/"
    print("Post entry ", posts_path + filename)
    if args.overwrite is False and os.path.isfile(posts_path + filename):
        continue

    if get_dir_id(entry) is None:
        print(f"No directory ID found for {entry.title}")
        continue

    with open(posts_path + filename, "w") as outfile:
        print("Writing " + filename)
        outfile.write(post_header(entry))

        html = process_html(entry.summary, repo_path)

        outfile.write(html)
        outfile.write("\n")
