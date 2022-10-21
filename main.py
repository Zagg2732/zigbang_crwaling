# https://heodolf.tistory.com/69?category=897877 를 참고함

import json
import datetime
import os
import re


import requests
from openpyxl import Workbook
from openpyxl.utils.exceptions import IllegalCharacterError

# api examples
SUBWAY_LIST_URL = "https://apis.zigbang.com/property/biglab/subway/all?"  # 직방의 지하철역 리스트 api
# ROOM_LIST_URL = "https://apis.zigbang.com/v3/items/ad/{subway_id}?subway_id={subway_id}&radius=1&sales_type=&deposit_s=0&rent_s=0&floor=1~%7Crooftop%7Csemibase&domain=zigbang&detail=false"
# ROOM_INFO_URL = "https://apis.zigbang.com/v2/items/{room_id}"

SALES_TYPE = '전세'  # 전세, 월세, 전세|월세, 매매 ...
RADIUS = 1.1  # 검색 거리

### GLOBAL ###
already_crawled_set = {}  # 이미 크롤링했던 room_id 들 필터링하기위한 set

### FILENAME ###
DIR = './files/크롤링'
now = datetime.datetime.now()
now_date = now.strftime('%Y%m%d_%H%M%S')
FILE_NAME = DIR + now_date + '.xlsx'

# https://www.zigbang.com/home/oneroom/items/33749522

def get_already_crwaled_id_set():  # 기존 크롤링했던 id set update
    global already_crawled_set
    f = open('./files/크롤링했던아이디.txt', 'r')

    origin_text = f.readline()

    f.close()

    already_crawled_list = origin_text.split(',')
    already_crawled_set = set(already_crawled_list)  # 이미 크롤링한 리스트 set 자료형으로 변경


def get_subway_ids():  # 직방 api의 지하철역 { 이름 : id } 값 가져오기
    res = requests.get(SUBWAY_LIST_URL)
    subway_json = json.loads(res.text)
    subway_set = {}
    for subway in subway_json:
        subway_set[str(subway['name'])] = subway['id']
    return subway_set


def get_subway_list(subway_id_set): # 내가 원하는 지하철역 id 정보 필터
    f = open('./files/crawl_subways.txt', 'r', encoding='utf-8')
    subway_list = f.readline().split(',')
    subway_ids = []
    for subway_name in subway_list:
        subway_ids.append(subway_id_set[subway_name + '역'])
    return subway_ids


def get_room_number_list(subway_id_list):  # 지하철역 주변 방정보 크롤링
    room_id_list = []
    for s_id in subway_id_list:
        res = requests.get(
            f'https://apis.zigbang.com/v3/items/ad/{s_id}?subway_id={s_id}&radius={RADIUS}&sales_type={SALES_TYPE}&deposit_s=0&rent_s=0&floor=1~%7Crooftop%7Csemibase&domain=zigbang&detail=false')
        room_id_json = json.loads(res.text)
        room_info_list = room_id_json['list_items']
        try:
            for info in room_info_list:
                room_id_list.append(info['simple_item']['item_id'])
        except Exception: # room_id_json['list_items'] 이 없는방(이벤트방으로 추정)이 존재해서 예외처리
            continue
    return room_id_list


def get_final_info_by_room_id_list(id_list): # room_id 로 디테일정보 구하기
    global already_crawled_set
    f = open("./files/크롤링했던아이디.txt", 'r+')
    crawl_id_text = ''

    info_list = []
    for idx, room_id in enumerate(id_list):
        print(f'{idx}/{len(id_list)}')
        if str(room_id) in already_crawled_set:  # 이미 크롤링한적이있는 room_id는 pass
            continue
        else:
            already_crawled_set.add(str(room_id))
            crawl_id_text += f',{room_id}'

        url = f'https://apis.zigbang.com/v2/items/{room_id}'
        res = requests.get(url)
        info_json = json.loads(res.text)
        try:
            service_type = info_json['item']['service_type']
        except Exception:
            print(f'info_json에 item이 없어서 나온에러일듯\n{info_json}')
            continue

        # 직방은 service_type별로 사용자의 url 링크가 달라져서 그에따른 s_type 적용
        s_type = None
        if service_type == '원룸':
            s_type = 'oneroom'
        elif service_type == '빌라':
            s_type = 'villa'
        elif service_type == '오피스텔':
            s_type = 'officetel'
        else:
            print(f'일치하지않는 service_type = "{service_type}" 으로 pass됨')
            continue
        type = info_json['item']['sales_type']
        if type == '월세':  # 전세로 검색해도 월세가 껴있는경우가있어서 pass처리
            continue
        amount = info_json['item']['보증금액']
        z_m2 = info_json['item']['전용면적_m2']
        g_m2 = info_json['item']['공급면적_m2']
        text = info_json['item']['description']
        text = re.sub('[\r\n😊🗨🤙💗⭐=☝✔❗★❤✅➖◈▶⭕⚠❌▒Ω♥💯♣🏠🍓💟📌▨🌈■◆🥝💙]', '', text)
        condition1 = text.find('중기청')
        condition2 = text.find('중소기업')
        if condition1 > 0 or condition2 > 0:
            while text.find('&#') > -1:
                start = text.find('&#')
                text = text[:start] + text[start + 9:]
            while text.find('&12') > -1:
                start = text.find('&12')
                text = text[:start] + text[start + 8:]
            room_info = {
                'url': f'https://www.zigbang.com/home/{s_type}/items/{room_id}',
                '타입': type,
                '보증금': amount,
                '전용면적': z_m2,
                '공급면적': g_m2,
                '설명': text
            }
            info_list.append(room_info)
    f.write(crawl_id_text)
    f.close()

    # info_list = sorted(info_list, key= lambda x: x['보증금'], reverse=True)
    # 보증금, 전용면적 순으로 sort
    info_list = sorted(info_list, key=lambda k: (k['보증금'], k['전용면적']), reverse=True)
    return info_list


# 'https://www.zigbang.com/home/officetel/items/33754312?isShare=true&shareUserNo=15916721&stamp=221019091840&share=true'
# 'https://www.zigbang.com/home/officetel/items/33754312?isShare=true&share=true'
# 'https://www.zigbang.com/home/villa/items/33773669'

def make_excel(room_info):
    global DIR
    write_wb = Workbook()  # openpyxl
    write_ws = write_wb.active

    # 컬럼 생성
    write_ws.append(list(room_info[0].keys()))

    # 크롤링 내용 삽입
    for info in room_info:
        excel_insert = []
        for value in info.values():
            excel_insert.append(value)
        try:
            write_ws.append(excel_insert)
        except IllegalCharacterError as e:  # 가끔 excel 형식의 Unicode에 맞지않는 문자가 포함된 공고가 있어서 예외처리
            print('IllegalCharacterError from {}'.format(excel_insert))

    # 엑셀 저장
    now = datetime.datetime.now()
    now_date = now.strftime('%Y%m%d_%H%M%S')

    if not os.path.exists(DIR):  # 폴더 없으면 만들기
        os.makedirs(DIR)

    excel_title = FILE_NAME

    write_wb.save(excel_title)


already_crwaled_id_set = get_already_crwaled_id_set()
subways = get_subway_ids()  # 지하철역 id
crawl_subway_id_list = get_subway_list(subways)  # 원하는 지하철역 id 만 구하기
room_id_list = get_room_number_list(crawl_subway_id_list)  # 지하철역 id로 매물id 구하기
final_info_list = get_final_info_by_room_id_list(room_id_list)
make_excel(final_info_list)
