import requests
import json, os, sys
import datetime
from login_utils import validate_tokens, generate_tokens


class BasicElement:
    def __init__(self, name=None, image=None):
        self.name = name
        self.image = image

    def __str__(self):
        return f"{self.name}"


class Schedule:
    def __init__(self):
        self.mode = None
        self.start = None
        self.end = None

        # Battle Schedules
        self.rule = None
        self.stages = []

        # Coop Schedules
        self.stage = BasicElement()
        self.weapons = []

    def __str__(self):
        start_time_str = self.start.strftime("%Y-%-m-%-d %-H:%Mから")
        if self.mode == 'coop':
            return f"{self.mode} {start_time_str} {self.stage}　{self.weapons[0]} {self.weapons[1]} {self.weapons[2]} {self.weapons[3]}"
        else:
            return f"{self.mode} {self.rule} {start_time_str} {self.stages[0]} {self.stages[1]}"

    def __repr__(self):
        return self.__str__()


class Gear:
    def __init__(self):
        self.info = BasicElement()
        self.brand = BasicElement()
        self.main_power = BasicElement()
        self.easy_power = BasicElement()
        self.slot = 0
        self.price = 0
        self.is_daily = False
        self.end = None
        self.type = None
        self.left_time = None

    def __str__(self):
        end_time = (self.end - datetime.datetime.now())
        return f"あと{end_time.seconds // 3600}時間{(end_time.seconds % 3600) // 60}分 {self.brand.name} {self.info.name} {self.price} {self.main_power}　{self.slot}"



self_path = os.path.dirname(__file__)
config_path = os.path.join(self_path, "config.txt")

config_file = open(config_path, "r")
config_data = json.load(config_file)
config_file.close()

WEB_SERVICE_TOKEN = config_data["web_service_token"]
BULLET_TOKEN = config_data["bullet_token"]
USER_LANGUAGE = config_data["user_language"]
SPLA3_API_URL = config_data["spla3_api_url"]
SPLA3_API_GRAPHQL_URL = SPLA3_API_URL + '/api/graphql'
WEB_VIEW_VERSION = config_data["web_view_version"]
NSO_APP_VERSION = config_data["nso_app_version"]

USER_AGENT = 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'

query_id = {
    "StageScheduleQuery": "730cd98e84f1030d3e9ac86b6f1aae13",
    "GesotownQuery": "a43dd44899a09013bcfd29b4b13314ff"
}

BATTLE_MODE = ("regular", "open", "challenge", "xmatch", "league", "fest")

TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
UTC_TO_JST = datetime.timedelta(hours=9)


def load_tokens():
    config_file = open(config_path, "r")
    config_data = json.load(config_file)
    config_file.close()

    global WEB_SERVICE_TOKEN, BULLET_TOKEN
    WEB_SERVICE_TOKEN = config_data["web_service_token"]
    BULLET_TOKEN = config_data["bullet_token"]


def generate_graphql_request(request_item):
    header = {
        'User-Agent': USER_AGENT,
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': USER_LANGUAGE,
        'Content-Type': 'application/json',
        'Origin': SPLA3_API_URL,
        'X-Web-View-Ver': WEB_VIEW_VERSION,
        'Authorization': f'Bearer {BULLET_TOKEN}'
    }
    cookie = {
        '_dnt': "0",
        '_gtoken': WEB_SERVICE_TOKEN
    }

    request_hash = query_id[request_item]

    body = {
        'extensions': {
            'persistedQuery': {
                'sha256Hash': request_hash,
                'version': '1'
            }
        },
        'variables': {}
    }

    return header, cookie, body


def get_stages(mode, repeat=3):
    '''
    Fetches regular, bankara, X-match, (league) battle schedules and coop schedule.
    '''

    if not validate_tokens():
        generate_tokens()
        load_tokens()

    header, cookie, body = generate_graphql_request('StageScheduleQuery')
    response = requests.post(SPLA3_API_GRAPHQL_URL, headers=header, cookies=cookie, json=body)
    if response.status_code != 200:
        raise Exception("Request Failed!")

    schedule_list = []

    if mode in BATTLE_MODE:
        mode_schedules, mode_setting = get_stage_index_string(mode)
        is_fest = json.loads(response.text)["data"]["currentFest"]
        if is_fest:
            schedule_list.append("フェス期間中だよ！")
        # TODO: return fest schedules
        else:
            schedules = json.loads(response.text)["data"][mode_schedules]["nodes"]
            repeat = min(repeat, len(schedules))
            schedule_list = get_battle_stages_helper(mode, schedules, mode_setting, repeat)

    elif mode == "coop":
        mode_schedules, regular, bigrun = get_stage_index_string(mode)
        schedules = json.loads(response.text)["data"][mode_schedules][regular]["nodes"]
        if not schedules:
            json.loads(response.text)["data"][mode_schedules][bigrun]["nodes"]
        # repeat = min(repeat, len(schedules))
        repeat = 1
        schedule_list = get_coop_stages_helper(mode, schedules, repeat)

    return schedule_list



def get_stage_index_string(mode):
    if mode == 'regular':
        return "regularSchedules", "regularMatchSetting"
    elif mode in ('open', 'challenge'):
        return "bankaraSchedules", "bankaraMatchSettings"
    elif mode == 'xmatch':
        return "xSchedules", "xMatchSetting"
    elif mode == 'league':
        return "leagueSchedules", "leagueMatchSetting"
    elif mode == 'fest':
        return "festSchedules", "festMatchSetting"
    elif mode == 'coop':
        return "coopGroupingSchedule", "regularSchedules", "bigRunSchedules"



def get_battle_stages_helper(mode, schedules, mode_setting, repeat):
    '''
    A helper function for loading data from json response.
    '''

    schedule_list = []
    if mode in ("open", "challenge"):
        bankara_idx = {"challenge":0, "open":1}
        for i in range(repeat):
            schedule = Schedule()
            schedule.mode = mode
            schedule.start = datetime.datetime.strptime(schedules[i]["startTime"], TIME_FORMAT) + UTC_TO_JST
            schedule.end = datetime.datetime.strptime(schedules[i]["endTime"], TIME_FORMAT) + UTC_TO_JST

            # rule = schedules[i][mode_setting][bankara_idx[mode]]["vsRule"]["rule"]
            schedule.rule = schedules[i][mode_setting][bankara_idx[mode]]["vsRule"]["name"]

            for j in range(2):
                stage_name = schedules[i][mode_setting][bankara_idx[mode]]["vsStages"][j]["name"]
                stage_image = schedules[i][mode_setting][bankara_idx[mode]]["vsStages"][j]["image"]["url"]
                stage = BasicElement(stage_name, stage_image)
                schedule.stages.append(stage)

            schedule_list.append(schedule)
    else:
        for i in range(repeat):
            schedule = Schedule()
            schedule.mode = mode
            schedule.start = datetime.datetime.strptime(schedules[i]["startTime"], TIME_FORMAT) + UTC_TO_JST
            schedule.end = datetime.datetime.strptime(schedules[i]["endTime"], TIME_FORMAT) + UTC_TO_JST

            if mode == 'regular':
                schedule.rule = 'ナワバリ'
            else:
                # rule = schedules[i][mode_setting]["vsRule"]["rule"]
                schedule.rule = schedules[i][mode_setting]["vsRule"]["name"]

            for j in range(2):
                stage_name = schedules[i][mode_setting]["vsStages"][j]["name"]
                stage_image = schedules[i][mode_setting]["vsStages"][j]["image"]["url"]
                stage = BasicElement(stage_name, stage_image)
                schedule.stages.append(stage)

            schedule_list.append(schedule)

    return schedule_list



def get_coop_stages_helper(mode, schedules, repeat):
    '''
    A helper function for loading data from json response.
    '''

    schedule_list = []

    for i in range(repeat):
        schedule = Schedule()
        schedule.mode = mode
        schedule.start = datetime.datetime.strptime(schedules[i]["startTime"], TIME_FORMAT) + UTC_TO_JST
        schedule.end = datetime.datetime.strptime(schedules[i]["endTime"], TIME_FORMAT) + UTC_TO_JST

        schedule.stage.name = schedules[i]["setting"]["coopStage"]["name"]
        schedule.stage.image = schedules[i]["setting"]["coopStage"]["image"]["url"]

        weapons = []
        for j in range(4):
            weapon_name = schedules[i]["setting"]["weapons"][j]["name"]
            weapon_image = schedules[i]["setting"]["weapons"][j]["image"]
            weapon = BasicElement(weapon_name, weapon_image)
            schedule.weapons.append(weapon)

        schedule_list.append(schedule)

    return schedule_list


def get_gesotown(only_daily=False, only_regular=False):
    '''
    Fetches sale gears in Gesotown.
    '''

    if not validate_tokens():
        generate_tokens()
        load_tokens()

    header, cookie, body = generate_graphql_request('GesotownQuery')
    response = requests.post(SPLA3_API_GRAPHQL_URL, headers=header, cookies=cookie, json=body)
    if response.status_code != 200:
        raise Exception("Request Failed!")

    gear_content = json.loads(response.text)

    daily_gear_data = gear_content["data"]["gesotown"]["pickupBrand"]["brandGears"]
    limit_gear_data = gear_content["data"]["gesotown"]["limitedGears"]

    daily_gear_list = get_gear_helper(daily_gear_data, True)
    limit_gear_list = get_gear_helper(limit_gear_data)

    if only_daily:
        return daily_gear_list
    if only_regular:
        return limit_gear_list
    return daily_gear_list + limit_gear_list


def get_gear_helper(data, is_daily=False):
    '''
    A helper function for loading gear info from json response.
    '''

    gear_list = []
    for gear_data in data:
        gear = Gear()
        gear.info.name = gear_data["gear"]["name"]
        gear.info.image = gear_data["gear"]["image"]["url"]
        gear.brand.name = gear_data["gear"]["brand"]["name"]
        gear.brand.image = gear_data["gear"]["brand"]["image"]["url"]
        gear.main_power.name = gear_data["gear"]["primaryGearPower"]["name"]
        gear.main_power.image = gear_data["gear"]["primaryGearPower"]["image"]["url"]
        gear.end = datetime.datetime.strptime(gear_data["saleEndTime"], TIME_FORMAT) + UTC_TO_JST
        gear.left_time = f"{(gear.end - datetime.datetime.now()).seconds // 3600}時間{((gear.end - datetime.datetime.now()).seconds % 3600) // 60}分"
        gear.price = gear_data["price"]
        gear.type = gear_data["gear"]["__typename"]
        gear.is_daily = is_daily
        gear.slot = len(gear_data["gear"]["additionalGearPowers"])
        gear_list.append(gear)

    return gear_list




# for test
if __name__ == '__main__':
    battle_rules =  ["regular", "open", "challenge", "xmatch", "league"]
    rules = ["coop"]
    for rule in battle_rules + rules:
        lst = get_stages(rule)
        for i in lst:
            print(i)

    lst2 = get_gesotown()
    for i in lst2:
        print(i)
    sys.exit(0)