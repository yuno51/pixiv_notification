import requests
import json
import datetime
import pytz
import os
import shutil


from pixivpy3 import AppPixivAPI
from pixivpy3.papi import PixivAPI
from pixivpy3.api import BasePixivAPI

import tokens


#pixiv
access_token = tokens.pixiv_access_token
refresh_token= tokens.pixiv_refresh_token


#push ballet
#https://www.pushbullet.com/#settings/account
bp_token = tokens.pushballet_token



saving_dir_path = "imgs"


searchtag_json = open("search_words.json", "r", encoding="utf-8_sig")
searchtag_list  = json.load(searchtag_json)["searchtag_list"]

def login():
    aapi = AppPixivAPI()
    aapi.auth(refresh_token=refresh_token)
    return aapi

def push_message(title, body):

    #https://www.pushbullet.com/#settings/account
    url = "https://api.pushbullet.com/v2/pushes"

    headers = {"content-type": "application/json", "Authorization": 'Bearer '+bp_token}

    data_send = {"type": "note", "title": title, "body": body}
    r = requests.post(url, headers=headers, data=json.dumps(data_send))

def push_image(image_path, extension):
    try:
        #upload
        url = "https://api.pushbullet.com/v2/upload-request"
        headers = {
            'Access-Token': bp_token,
            'Content-Type': 'application/json'
        }

        json_data = {
            'file_name': image_path,
            'file_type': f'image/{extension}'
        }

        response = requests.post(url, headers=headers, json=json_data).json()
        #pprint.pprint(response)
        file_name = response["file_name"]
        file_type = response["file_type"]
        file_url = response["file_url"]
        upload_url = response["upload_url"]

        response = requests.post(upload_url, data=response["data"], files={"file":open(image_path, "rb")})

        #create push
        url = "https://api.pushbullet.com/v2/pushes"
        headers = {
            'Access-Token': bp_token,
            'Content-Type': 'application/json'
        }
        json_data = {
            'type': 'file',
            'file_name': file_name,
            'file_type': file_type,
            'file_url': file_url,
        }
        res = requests.post(url, headers=headers, json=json_data)

    except Exception as e:
        print(e)

def download_imgaes(aapi,id,urls):
    file_names = []
    for i,img_url in enumerate(urls):
        file_name = f"{id}_{i}.jpg"
        file_names.append(file_name)
        res = aapi.download(img_url, path=saving_dir_path, name=file_name, replace=True)
        if not res:
            print(res, id)
    return file_names

def get_img_urls(content_dict):
    img_urls = []
    if not content_dict["meta_pages"]: #空 :1枚の画像
        img_urls.append(content_dict['image_urls']['large'])
    else:
        for meta_page in content_dict["meta_pages"]:
            img_urls.append(meta_page['image_urls']['large'])
    return tuple(img_urls)

def clear_imgs_folder():
    shutil.rmtree('imgs')
    os.mkdir('imgs')

def search_new_contents(aapi, searchtag, contents_set, mode='illusts'):
    def time_calcu(create_date, yesterday):
        Y, m, d, H, M, S = int(create_date[:4]), int(create_date[5:7]), int(create_date[8:10]), int(create_date[11:13]), int(create_date[14:16]), int(create_date[17:19])
        create_date = datetime.datetime(Y, m, d, H, M, S).replace(tzinfo=pytz.timezone('Asia/Tokyo'))
        #pixivの時間はherokuでも日本時間
        return create_date > yesterday #遅い方がTrue

    now = datetime.datetime.now().astimezone(pytz.timezone('Asia/Tokyo')) #tokyoの時刻に
    yesterday = now - datetime.timedelta(days=1)
    search_start_time = yesterday.strftime('%Y-%m-%d')
    try:
        if mode == 'illusts':
            result = aapi.search_illust(searchtag, start_date=search_start_time, end_date=None)
            result = result[mode]
        else:
            result = aapi.search_novel(searchtag, start_date=search_start_time, end_date=None)
            result = result[mode]
            

        for content_dict in result:
            create_date = content_dict['create_date']
            id = content_dict["id"]
            title = content_dict["title"]

            
            if time_calcu(create_date, yesterday):
                print(searchtag,title)
                if mode == 'illusts':
                    urls = get_img_urls(content_dict)
                    contents_set.add((title,id,urls))
                else:
                    try:
                        series = content_dict['series']['title'] + " "
                    except:
                        series = ""
                    tags = []                    
                    for tag in content_dict['tags']:
                        tags.append(tag['name'])
                    contents_set.add((f"{series}{title}",id,tuple(tags)))
    except Exception as e:
        print(e)
     

    return contents_set



def main():
    
    headers = {'Access-Token': bp_token}
    response = requests.delete('https://api.pushbullet.com/v2/pushes', headers=headers)

    if not os.path.exists("imgs"):
        os.mkdir("imgs")

    aapi = login()

    new_illust_ids = set()
    new_novel_ids = set()

    print("-"*20 + "search artworks and novels" + "-"*20)
    
    for searchtag in searchtag_list:
        #print(f"search word : {searchtag}")
        new_illust_ids = search_new_contents(aapi, searchtag, new_illust_ids, mode='illusts')
        new_novel_ids = search_new_contents(aapi, searchtag, new_novel_ids, mode='novels')

    #pprint.pprint(new_illust_ids)
    #pprint.pprint(new_novel_ids)

    print("-"*20 + "push notification" + "-"*20)

    for (title,id,urls) in new_illust_ids:
        artwork_url = f"https://www.pixiv.net/artworks/{id}"
        push_message("pixiv", f"{title}\n{artwork_url}")
        file_names = download_imgaes(aapi,id,urls)

        for file_name in file_names:
            push_image(f"imgs/{file_name}", "jpg")

    for (title,id,tags) in new_novel_ids:
        novel_url = f"https://www.pixiv.net/novel/show.php?id={id}"
        tag_string = " ".join(tags)
        push_message("pixiv", f"{title}\n{novel_url}\n{tag_string}")

    clear_imgs_folder()
    

main()

#push_message("line","test")


