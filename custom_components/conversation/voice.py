import logging, re, aiohttp
from homeassistant.helpers import intent
import homeassistant.config as conf_util
from homeassistant.helpers import template, entity_registry, area_registry
from homeassistant.helpers.network import get_url
# 授权
from typing import Optional
import homeassistant.auth.models as models
from homeassistant.auth.const import ACCESS_TOKEN_EXPIRATION
from datetime import timedelta

from .box.aligenie_view import AliGenieView
from .box.tmall_view import TmallView
from .box.xiaoai_view import XiaoaiGateView
from .box.xiaodu_view import XiaoduGateView

from .util import VERSION, DOMAIN, DATA_AGENT, DATA_CONFIG, XIAOAI_API, TMALL_API, ALIGENIE_API, XIAODU_API, VIDEO_API, \
    ApiConfig, find_entity, trim_char, http_get, get_local_video_url, \
    matcher_brightness, matcher_light_color, matcher_light_mode, \
    matcher_watch_video, matcher_watch_movie, matcher_watch_tv, \
    matcher_script, matcher_automation, matcher_media_player, matcher_query_state, matcher_switch, matcher_on_off

_LOGGER = logging.getLogger(__name__)

def text_start(findText, text):
    return text.find(findText,0,len(findText)) >= 0

class Voice():

    def __init__(self, hass):
        self.hass = hass
        self.api_config = ApiConfig(hass.config.path(".shaonianzhentan"))
        hass.services.async_register(DOMAIN, 'reload', self.reload)
        hass.services.async_register(DOMAIN, 'setting', self.setting)
        # 显示插件信息
        _LOGGER.info('''
    -------------------------------------------------------------------
        语音小助手【作者QQ：635147515】
        
        版本：''' + VERSION + '''
        
        介绍：官方语音助手修改增强版
        
        项目地址：https://github.com/shaonianzhentan/conversation

    -------------------------------------------------------------------''')
        local = hass.config.path("custom_components/conversation/dist")
        hass.http.register_static_path('/conversation', local, False)
        hass.http.register_view(XiaoaiGateView)
        hass.http.register_view(AliGenieView)
        hass.http.register_view(XiaoduGateView)
        hass.http.register_view(TmallView)
        # 重写刷新token方法
        hass.auth._store.async_create_refresh_token = self.async_create_refresh_token

    # 创建刷新token
    async def async_create_refresh_token(
        self,
        user: models.User, 
        client_id: Optional[str] = None,
        client_name: Optional[str] = None,
        client_icon: Optional[str] = None,
        token_type: str = models.TOKEN_TYPE_NORMAL,
        access_token_expiration: timedelta = ACCESS_TOKEN_EXPIRATION,
        credential: models.Credentials = None,
    ) -> models.RefreshToken:
        # 如果是小度或天猫精灵，则给它们十年的授权
        if client_id is not None and ['https://open.bot.tmall.com', 'https://xiaodu.baidu.com'].count(client_id.strip('/')) > 0:
            access_token_expiration = timedelta(hours=87600)
            _LOGGER.debug('如果是小度或天猫精灵，则给它们十年的授权')
        """Create a new token for a user."""
        kwargs = {
            'user': user,
            'client_id': client_id,
            'token_type': token_type,
            'access_token_expiration': access_token_expiration
        }  # type: Dict[str, Any]
        if client_name:
            kwargs['client_name'] = client_name
        if client_icon:
            kwargs['client_icon'] = client_icon

        refresh_token = models.RefreshToken(**kwargs)
        user.refresh_tokens[refresh_token.id] = refresh_token

        self.hass.auth._store._async_schedule_save()
        return refresh_token
                
    # 获取基础url
    def get_base_url(self, url):
        try:
            base_url = get_url(self.hass)
        except Exception as ex:
            base_url = 'http://localhost:8123'
        return f'{base_url}{url}'

    @property
    def media_player(self):
        ''' 媒体播放器 '''
        cfg = self.api_config.get_config()
        entity_id = cfg.get('media_player', '')
        if entity_id != '':
            state = self.hass.states.get(entity_id)
            if state is not None:
                return state
        return None

    # 解析模板
    def template(self, message):
        tpl = template.Template(message, self.hass)
        return tpl.async_render(None)

    # 返回意图结果
    def intent_result(self, message, extra_data = None):
        intent_result = intent.IntentResponse()
        intent_result.async_set_speech(message, 'plain', extra_data)
        return intent_result

    # 重新加载配置
    async def reload(self, service):
        hass = self.hass
        # 读取配置
        hass.data[DATA_CONFIG] = await conf_util.async_hass_config_yaml(hass)
        # 清除agent
        hass.data[DATA_AGENT] = None

    # 异步调用服务
    def call_service(self, service, data={}):
        arr = service.split('.')
        self.hass.async_create_task(self.hass.services.async_call(arr[0], arr[1], data))

    # 语音服务处理
    async def async_process(self, text):
        # 去掉前后标点符号
        _text = self.fire_text(text)

        # 查询设备状态
        intent_result = await self.execute_query_state(_text)
        if intent_result is not None:
            return intent_result
        
        # 灯光颜色控制
        intent_result = await self.execute_light_color(_text)
        if intent_result is not None:
            return intent_result

        # 灯光模式控制
        intent_result = await self.execute_light_mode(_text)
        if intent_result is not None:
            return intent_result

        # 灯光亮度控制
        intent_result = await self.execute_light_brightness(_text)
        if intent_result is not None:
            return intent_result

        # 执行脚本
        intent_result = await self.execute_script(_text)
        if intent_result is not None:
            return intent_result
        
        # 自动化操作
        intent_result = await self.execute_automation(_text)
        if intent_result is not None:
            return intent_result

        # 媒体播放器控制
        intent_result = await self.execute_media_player(_text)
        if intent_result is not None:
            return intent_result

        # 开关同时控制
        intent_result = await self.execute_on_off(_text)
        if intent_result is not None:
            return intent_result

        # 开关控制
        intent_result = await self.execute_switch(_text)
        if intent_result is not None:
            return intent_result

        # 执行自定义语句
        intent_result = await self.execute_action(_text)
        if intent_result is not None:
            return intent_result

        # 调用聊天机器人
        message = await self.chat_robot(text)
        return self.intent_result(message)

    # 触发事件
    def fire_text(self, text):
        hass = self.hass
        # 数字转换汉字
        matchObj = re.match(r'(上|下|前|后|左|右)1(曲|首|个|页|条|段)', text)
        if matchObj is not None:
            text = text.replace('1', '一')

        # 发送事件，共享给其他组件
        text_data = { 'text': text }
        # 语义解析
        result = matcher_watch_tv(text)
        if result is not None:
            text_data.update({ 'type': 'iptv', 'value': result })

        hass.bus.fire('conversation', text_data)
        # 调用python_script.conversation
        if hass.services.has_service('python_script', 'conversation'):
            hass.async_create_task(hass.services.async_call('python_script', 'conversation', text_data))
        return text

    # 查看设备
    def query_device(self, text):
        hass = self.hass
        device_type = None
        if text == '查看全部设备' or text == '查看所有设备':
            device_type = ''
        elif text == '查看全部灯' or text == '查看所有灯':
            device_type = '.light'
        elif text == '查看全部传感器' or text == '查看所有传感器':
            device_type = '.sensor'
        elif text == '查看全部开关' or text == '查看所有开关':
            device_type = '.switch'
        elif text == '查看全部脚本' or text == '查看所有脚本':
            device_type = '.script'
        elif text == '查看全部自动化' or text == '查看所有自动化':
            device_type = '.automation'
        elif text == '查看全部场景' or text == '查看所有场景':
            device_type = '.scene'

        if device_type is not None:
            return self.intent_result(text.replace('查看', ''), {
                'type': 'entity',
                'data': self.template('{%- for state in states' + device_type + ' -%} "{{ state.entity_id }}",{%- endfor -%}')
            })
        return None

    # 执行动作
    async def execute_action(self, text):
        hass = self.hass
        if text == '重新加载配置':
            self.reload()
            return self.intent_result("重新加载配置成功")

        # 如果有查询到设备，则返回
        device_result = self.query_device(text)
        if device_result is not None:
            return device_result

        # 遍历所有实体
        states = hass.states.async_all()
        for state in states:
            entity_id = state.entity_id
            attributes = state.attributes
            state_value = state.state
            friendly_name = attributes.get('friendly_name')
            # 执行自定义脚本
            if entity_id.find('script.') == 0:
                cmd = friendly_name.split('=')
                if cmd.count(text) > 0:
                    arr = entity_id.split('.')
                    # _LOGGER.debug('执行脚本：' + entity_id)
                    await hass.services.async_call(arr[0], arr[1])
                    return self.intent_result(f"正在执行自定义脚本：{entity_id}", {
                        'type': 'entity',
                        'data': [ entity_id ]
                    })
            # 查询设备状态
            if friendly_name is not None:
                friendly_name_lower = friendly_name.lower()
                # 设备状态
                if text.lower() == friendly_name_lower:
                    return self.intent_result(friendly_name + '的信息', {
                        'type': 'entity',
                        'data': [ entity_id ]
                    })
                # 查询设备属性
                if text.lower() == friendly_name_lower + '的属性':
                    return self.intent_result(friendly_name + '的属性', {
                        'type': 'entity',
                        'data': [ entity_id ]
                    })
                # 查询摄像监控画面
                if text.lower() == '查看' + friendly_name_lower + '的画面':
                    return self.intent_result(friendly_name_lower + '的画面', {
                        'type': 'entity',
                        'data': [ entity_id ]
                    })
        return None
    
    # 执行灯光调色
    async def execute_light_color(self, text):
        result = matcher_light_color(text)
        if result is not None:
            state = await find_entity(self.hass, result[0], 'light')
            if state is not None:
                self.call_service('light.turn_on', {
                    'entity_id': state.entity_id,
                    'color_name': result[1]
                })
                return self.intent_result(f"已经设置为{result[2]}色", {
                        'type': 'entity',
                        'data': [ state.entity_id ]
                    })

    # 执行灯光模式
    async def execute_light_mode(self, text):
        result = matcher_light_mode(text)
        if result is not None:
            state = await find_entity(self.hass, result[0], 'light')
            if state is not None:
                self.call_service('light.turn_on', {
                    'entity_id': state.entity_id,
                    'effect': result[1]
                })
                return self.intent_result(f"已经设置为{result[2]}模式", {
                        'type': 'entity',
                        'data': [ state.entity_id ]
                    })
    
    # 执行灯光亮度
    async def execute_light_brightness(self, text):
        result = matcher_brightness(text)
        if result is not None:
            state = await find_entity(self.hass, result[0], 'light')
            if state is not None:
                self.call_service('light.turn_on', {
                    'entity_id': state.entity_id,
                    'brightness_pct': result[1]
                })
                return self.intent_result(f"亮度已经设置为{result[1]}%", {
                        'type': 'entity',
                        'data': [ state.entity_id ]
                    })
    # 执行脚本
    async def execute_script(self, text):
        result = matcher_script(text)
        if result is not None:
            # 遍历所有实体
            states = self.hass.states.async_all()
            for state in states:
                entity_id = state.entity_id
                attributes = state.attributes
                state_value = state.state
                friendly_name = attributes.get('friendly_name')
                # 执行自定义脚本
                if entity_id.find('script.') == 0:
                    cmd = friendly_name.split('=')
                    if cmd.count(result) > 0:
                        self.call_service(entity_id)
                        return self.intent_result("正在执行自定义脚本：" + entity_id, {
                            'type': 'entity',
                            'data': [ entity_id ]
                        })

    # (执行|触发|打开|关闭|切换)自动化
    async def execute_automation(self, text):
        result = matcher_automation(text)
        if result is not None:
            action = result[0]
            state = await find_entity(self.hass, result[1], 'automation')
            if state is not None:
                entity_id = state.entity_id
                extra_data = {
                    'type': 'entity',
                    'data': [ entity_id ]
                }
                service_data = {'entity_id': entity_id}
                if action == '执行' or action == '触发':
                    self.call_service('automation.trigger', service_data)
                    return self.intent_result("正在触发自动化：" + entity_id, extra_data)
                elif action == '打开':
                    self.call_service('automation.turn_on', service_data)
                    return self.intent_result("正在打开自动化：" + entity_id, extra_data)
                elif action == '关闭':
                    self.call_service('automation.turn_off', service_data)
                    return self.intent_result("正在关闭自动化：" + entity_id, extra_data)
                elif action == '切换':
                    self.call_service('automation.toggle', service_data)
                    return self.intent_result("正在切换自动化：" + entity_id, extra_data)

    # 媒体播放器(播放|暂停|下一曲|上一曲)
    async def execute_media_player(self, text):
        result = matcher_media_player(text)
        if result is not None:
            action = result[1]
            state = await find_entity(self.hass, result[0], 'media_player')
            if state is not None:
                entity_id = state.entity_id
                extra_data = {
                    'type': 'entity',
                    'data': [ entity_id ]
                }
                service_data = {'entity_id': entity_id}
                if action == '播放':
                    self.call_service('media_player.media_play', service_data)
                elif action == '暂停':
                    self.call_service('media_player.media_pause', service_data)
                elif action == '下一曲':
                    self.call_service('media_player.media_next_track', service_data)
                elif action == '上一曲':
                    self.call_service('media_player.media_previous_track', service_data)

                return self.intent_result(text, extra_data)
                
    # 查看设备状态
    async def execute_query_state(self, text):
        result = matcher_query_state(text)
        if result is not None:
            state = await find_entity(self.hass, result)
            if state is not None:
                attributes = state.attributes
                friendly_name = attributes.get('friendly_name')
                return self.intent_result(f"{friendly_name}的状态是：{state.state}", {
                    'type': 'entity',
                    'data': [ state.entity_id ]
                })

    # 同时开关
    async def execute_on_off(self, _text):
        hass = self.hass
        result = matcher_on_off(_text)
        if result is not None:
            result1 = await self.matcher_multiple_switch(result[0][1], result[0][0])
            result2 = await self.matcher_multiple_switch(result[1][1], result[1][0])
            if result1 is not None or result2 is not None:
                return self.intent_result(f"执行成功")

    # 执行开关
    async def execute_switch(self, _text):
        hass = self.hass
        result = matcher_switch(_text)
        if result is not None:                
            _name = result[0]
            service_type = result[1]
            intent_type = result[2]
            action_text = result[3]
            # 操作所有灯和开关
            if _name == '所有灯' or _name == '所有的灯' or _name == '全部灯' or _name == '全部的灯':
                # 灯
                light_entity = self.template('''
                    {% for state in states.light -%}
                        {{ state.entity_id }},
                    {%- endfor %}
                ''').strip(',')
                if light_entity != '':
                    self.call_service(f'light.{service_type}', { 'entity_id': light_entity })
                # 开关
                input_boolean_entity = self.template('''
                    {% for state in states.input_boolean -%}
                        {% if '灯' in state.attributes['friendly_name'] -%}
                            {{state.entity_id}},
                        {%- endif %}
                    {%- endfor %}
                ''').strip(' ,')
                if input_boolean_entity != '':
                    self.call_service(f'input_boolean.{service_type}', { 'entity_id': input_boolean_entity})
                # 开关
                switch_entity = self.template('''
                    {% for state in states.switch -%}
                        {% if '灯' in state.attributes['friendly_name'] -%}
                            {{state.entity_id}},
                        {%- endif %}
                    {%- endfor %}
                ''').strip(' ,')
                if switch_entity != '':
                    self.call_service(f'switch.{service_type}', { 'entity_id': switch_entity})

                return self.intent_result("正在" + _text, {
                            'type': 'entity',
                            'data': self.template('{%- for state in states.light -%} "{{ state.entity_id }}",{%- endfor -%}')
                        })
            elif _name == '所有开关' or _name == '所有的开关' or _name == '全部开关' or _name == '全部的开关':
                self.call_service(f'switch.{service_type}', {
                    'entity_id': self.template('{% for state in states.switch -%}{{ state.entity_id }},{%- endfor %}').strip(',')
                })
                self.call_service(f'input_boolean.{service_type}', {
                    'entity_id': self.template('{% for state in states.input_boolean -%}{{ state.entity_id }},{%- endfor %}').strip(',')
                })
                return self.intent_result("正在" + _text, {
                            'type': 'entity',
                            'data': self.template('''
                                {%- for state in states.switch -%} "{{ state.entity_id }}",{%- endfor -%}
                                {%- for state in states.input_boolean -%} "{{ state.entity_id }}",{%- endfor -%}
                            ''')
                        })
            else:
                # 当名称包含多个设备时执行
                result = await self.matcher_multiple_switch(_name, service_type)
                if result is not None:
                    return self.intent_result("正在执行" + result)
                # 如果没有这个设备，则返回为空
                state = await find_entity(self.hass, _name, ['input_boolean', 'light', 'switch', 'climate', 'fan', 'media_player'])
                if state is not None:
                    # 空调没有切换方法
                    if ['climate'].count(state.domain) == 1 and service_type == 'toggle':
                        return None
                    # 调用服务执行
                    self.call_service(f'{state.domain}.{service_type}', { 'entity_id': state.entity_id})
                    return self.intent_result(f"正在{action_text}{state.name}", {
                        'type': 'entity',
                        'data': [ state.entity_id ]
                    })

    # 执行多个开关
    async def matcher_multiple_switch(self, text, service_type):
        if isinstance(text, list):
            # 多个设备
            _list = []
            for _name in text:
                state = await find_entity(self.hass, _name, ['input_boolean', 'light', 'switch', 'climate', 'fan', 'media_player'])
                if state is not None:
                    _list.append(_name)
                    self.call_service(f'{state.domain}.{service_type}', {'entity_id': state.entity_id})
            if len(_list) > 0:
                return '、'.join(_list)
        elif text.count('灯') > 1:
            # 全是灯
            matchObj = re.findall(r'((.*?)灯)', text)
            _list = []
            for item in matchObj:
                # 这里去掉常用连接汉字
                _name = trim_char(item[0].strip('和跟'))
                print(_name)
                state = await find_entity(self.hass, _name, ['input_boolean', 'light', 'switch'])
                if state is not None:
                    _list.append(_name)
                    self.call_service(f'{state.domain}.{service_type}', {'entity_id': state.entity_id})
            if len(_list) > 0:
                return '、'.join(_list)

    # 聊天机器人
    async def chat_robot(self, text):
        message = "对不起，我不明白"
        try:
            async with aiohttp.request('GET','https://api.ownthink.com/bot?appid=xiaosi&spoken=' + text) as r:
                res = await r.json(content_type=None)
                _LOGGER.debug(res)
                message = res['data']['info']['text']
        except Exception as e:
            _LOGGER.debug(e)        
        return message

    # 配置设置
    async def setting(self, service):
        hass = self.hass
        is_save = False
        config_data = self.api_config.get_config()
        data = service.data
        # 保存user_id
        user_id = data.get('user_id')
        if user_id is not None:
            config_data.update({'user_id': user_id})
            is_save = True
        # 保存userOpenId
        userOpenId = data.get('userOpenId')
        if userOpenId is not None:
            config_data.update({'userOpenId': userOpenId})
            is_save = True
        # 保存aligenie
        aligenie = data.get('aligenie')
        if aligenie is not None:
            config_data.update({'aligenie': aligenie})
            is_save = True
        # 保存open_mic
        open_mic = data.get('open_mic')
        if open_mic is not None:
            config_data.update({'open_mic': open_mic})
            is_save = True
        # 保存apiKey
        apiKey = data.get('apiKey', '')
        if apiKey != '':
            config_data.update({'apiKey': apiKey})
            is_save = True
        # 保存配置
        if is_save:
            self.api_config.save_config(config_data)
            self.call_service('persistent_notification.create', {
                    'message': '配置信息保存成功',
                    'title': '语音小助手',
                    'notification_id': 'conversation-success'
                })

    # 记录语音识别语句
    async def set_state(self, text=VERSION, source = ''):
        hass = self.hass
        config_data = self.api_config.get_config()
        hass.states.async_set('conversation.voice', text, {
            "icon": "mdi:account-voice",
            "friendly_name": "语音助手",
            "source": source,
            "version": VERSION,
            "open_mic": config_data.get("open_mic", True),
            'link': self.get_base_url('/conversation/index.html?ver=' + VERSION),
            'XiaoAi': self.get_base_url(XIAOAI_API),
            'AliGenie': self.get_base_url(ALIGENIE_API),
            'XiaoDu': self.get_base_url(XIAODU_API),
            'Tmall': self.get_base_url(TMALL_API)
        })
