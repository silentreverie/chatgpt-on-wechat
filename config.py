# encoding:utf-8

import json
import os
from common.log import logger

config = {}


def load_config():
    global config
    config_path = "config.json"
    if not os.path.exists(config_path):
        raise Exception('配置文件不存在，请根据config-template.json模板创建config.json文件')

    config_str = read_file(config_path)
    # 将json字符串反序列化为dict类型
    config = json.loads(config_str)
    if not "name" in config:
        raise Exception('配置文件中不包含name')

    name = config["name"]
    #默认打开私人聊天
    config["single_chat_prefix"] = [name+"，", name]
    config["single_chat_reply_prefix"] = "[助理" + name + "]: "
    #config["single_chat_reply_prefix"] = "[助理]"

    #默认关闭群组功能，除非配置设置了
    if "group_name_white_list" in config and len(config["group_name_white_list"]) > 0:
        config["group_chat_prefix"] = [name+"，", name]
        config["group_chat_reply_prefix"] = "[助理" + name + "]: "

    logger.info("[INIT] load config: {}".format(config))



def get_root():
    return os.path.dirname(os.path.abspath( __file__ ))


def read_file(path):
    with open(path, mode='r', encoding='utf-8') as f:
        return f.read()


def conf():
    return config

