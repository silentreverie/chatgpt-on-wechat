# encoding:utf-8

"""
wechat channel
"""

import itchat
import json
from itchat.content import *
from channel.channel import Channel
from concurrent.futures import ThreadPoolExecutor
from common.log import logger
from common.tmp_dir import TmpDir
from config import conf
import requests
import io
import time

thread_pool = ThreadPoolExecutor(max_workers=8)


@itchat.msg_register(TEXT)
def handler_single_msg(msg):
    WechatChannel().handle_text(msg)
    return None


@itchat.msg_register(TEXT, isGroupChat=True)
def handler_group_msg(msg):
    WechatChannel().handle_group(msg)
    return None


@itchat.msg_register(VOICE)
def handler_single_voice(msg):
    WechatChannel().handle_voice(msg)
    return None


class WechatChannel(Channel):
    def __init__(self):
        pass

    def startup(self):
        # login by scan QRCode
        itchat.auto_login(enableCmdQR=2, hotReload=conf().get('hot_reload', False))

        # start message listener
        itchat.run()

    def handle_voice(self, msg):
        if conf().get('speech_recognition') != True :
            return
        logger.debug("[WX]receive voice msg: " + msg['FileName'])
        thread_pool.submit(self._do_handle_voice, msg)

    def _do_handle_voice(self, msg):
        from_user_id = msg['FromUserName']
        other_user_id = msg['User']['UserName']
        if from_user_id == other_user_id:
            file_name = TmpDir().path() + msg['FileName']
            msg.download(file_name)
            query = super().build_voice_to_text(file_name)
            if conf().get('voice_reply_voice'):
                self._do_send_voice(query, from_user_id)
            else:
                self._do_send_text(query, from_user_id)

    def handle_text(self, msg):
        logger.debug("[WX]receive text msg: " + json.dumps(msg, ensure_ascii=False))
        content = msg['Text']
        self._handle_single_msg(msg, content)

    def _handle_single_msg(self, msg, content):
        from_user_id = msg['FromUserName']
        to_user_id = msg['ToUserName']              # 接收人id
        other_user_id = msg['User']['UserName']     # 对手方id
        create_time = msg['CreateTime']             # 消息时间
        match_prefix = self.check_prefix(content, conf().get('single_chat_prefix'))
        #logger.info("content={} match_prefix={}".format(content, match_prefix))
        if conf().get('single_chat_auto_reply') == True and match_prefix is None:
            match_prefix = ''
        if conf().get('hot_reload') == True and int(create_time) < int(time.time()) - 60:    #跳过1分钟前的历史消息
            logger.debug("[WX]history message skipped")
            return
        if "」\n- - - - - - - - - - - - - - -" in content:
            logger.debug("[WX]reference query skipped")
            return
        if from_user_id == other_user_id and match_prefix is not None:
            # 好友向自己发送消息
            if match_prefix != '':
                str_list = content.split(match_prefix, 1)
                if len(str_list) == 2:
                    content = str_list[1].strip()

            img_match_prefix = self.check_prefix(content, conf().get('image_create_prefix'))
            if img_match_prefix:
                content = content.split(img_match_prefix, 1)[1].strip()
                thread_pool.submit(self._do_send_img, content, from_user_id)
            else :
                thread_pool.submit(self._do_send_text, content, from_user_id)
        elif to_user_id == other_user_id and match_prefix is not None:
            # 自己给好友发送消息
            str_list = content if (match_prefix== "") else content.split(match_prefix, 1)
            if len(str_list) == 2:
                content = str_list[1].strip()
            img_match_prefix = self.check_prefix(content, conf().get('image_create_prefix'))
            if img_match_prefix:
                content = content.split(img_match_prefix, 1)[1].strip()
                thread_pool.submit(self._do_send_img, content, to_user_id)
            else:
                thread_pool.submit(self._do_send_text, content, to_user_id)


    def handle_group(self, msg):
        logger.debug("[WX]receive group msg: " + json.dumps(msg, ensure_ascii=False))
        group_name = msg['User'].get('NickName', None)
        group_id = msg['User'].get('UserName', None)
        create_time = msg['CreateTime']             # 消息时间
        if conf().get('hot_reload') == True and int(create_time) < int(time.time()) - 60:    #跳过1分钟前的历史消息
            logger.debug("[WX]history group message skipped")
            return
        if not group_name:
            return ""
        origin_content = msg['Content']
        content = msg['Content']
        #content_list = content.split(' ', 1)
        context_special_list = content.split('\u2005', 1)
        if len(context_special_list) == 2:
            content = context_special_list[1]
        if "」\n- - - - - - - - - - - - - - -" in content:
            logger.debug("[WX]reference query skipped")
            return ""
        config = conf()
        match_prefix = (msg['IsAt'] and config.get("group_at_off", True)) \
            or self.check_prefix(origin_content, config.get('group_chat_prefix')) \
            or self.check_contain(origin_content, config.get('group_chat_keyword'))
        logger.info("content={} match_prefix={}".format(content, match_prefix))
        if ('ALL_GROUP' in config.get('group_name_white_list') 
            or group_name in config.get('group_name_white_list') 
            or self.check_contain(group_name, config.get('group_name_keyword_white_list'))) \
                and match_prefix: #match_prefix有两种形态，一种是true/false表示是否被@;一种是字符串表示是否被匹配
            #去掉前缀，但注意被@的情况
            if match_prefix == True:
                content = content if len(content.split(' ', 1)) <= 1 else content.split(' ', 1)[1]
            else:
                content = content.split(match_prefix, 1)[1]
            content = content.strip()

            img_match_prefix = self.check_prefix(content, conf().get('image_create_prefix'))
            logger.info("content={} after_match_prefix={}".format(content, img_match_prefix))
            if img_match_prefix:
                content = content.split(img_match_prefix, 1)[1].strip()
                thread_pool.submit(self._do_send_img, content, group_id)
            else:
                thread_pool.submit(self._do_send_group, content, msg)

    def send(self, msg, receiver):
        itchat.send(msg, toUserName=receiver)
        logger.info('[WX] sendMsg={}, receiver={}'.format(msg, receiver))

    def _do_send_voice(self, query, reply_user_id):
        try:
            if not query:
                return
            context = dict()
            context['from_user_id'] = reply_user_id
            reply_text = super().build_reply_content(query, context)
            if reply_text:
                replyFile = super().build_text_to_voice(reply_text)
                itchat.send_file(replyFile, toUserName=reply_user_id)
                logger.info('[WX] sendFile={}, receiver={}'.format(replyFile, reply_user_id))
        except Exception as e:
            logger.exception(e)

    def _do_send_text(self, query, reply_user_id):
        try:
            if not query:
                return
            context = dict()
            context['session_id'] = reply_user_id
            reply_text = super().build_reply_content(query, context)
            if reply_text:
                self.send(conf().get("single_chat_reply_prefix") + reply_text, reply_user_id)
        except Exception as e:
            logger.exception(e)

    def _do_send_img(self, query, reply_user_id):
        try:
            if not query:
                return
            context = dict()
            context['type'] = 'IMAGE_CREATE'
            img_url = super().build_reply_content(query, context)
            if not img_url:
                return

            # 图片下载
            pic_res = requests.get(img_url, stream=True)
            image_storage = io.BytesIO()
            for block in pic_res.iter_content(1024):
                image_storage.write(block)
            image_storage.seek(0)

            # 图片发送
            itchat.send_image(image_storage, reply_user_id)
            logger.info('[WX] sendImage, receiver={}'.format(reply_user_id))
        except Exception as e:
            logger.exception(e)

    def _do_send_group(self, query, msg):
        if not query:
            return
        context = dict()
        group_name = msg['User']['NickName']
        group_id = msg['User']['UserName']
        group_chat_in_one_session = conf().get('group_chat_in_one_session', [])
        if ('ALL_GROUP' in group_chat_in_one_session or \
                group_name in group_chat_in_one_session or \
                self.check_contain(group_name, group_chat_in_one_session)):
            context['session_id'] = group_id
        else:
            context['session_id'] = msg['ActualUserName']
        reply_text = super().build_reply_content(query, context)
        if reply_text:
            reply_text = '@' + msg['ActualNickName'] + ' ' + reply_text.strip()
            self.send(conf().get("group_chat_reply_prefix", "") + reply_text, group_id)


    def check_prefix(self, content, prefix_list):
        for prefix in prefix_list:
            if content.startswith(prefix):
                return prefix
        return None


    def check_contain(self, content, keyword_list):
        if not keyword_list:
            return None
        for ky in keyword_list:
            if content.find(ky) != -1:
                return True
        return None

