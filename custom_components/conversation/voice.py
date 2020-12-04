import logging, re, aiohttp
from homeassistant.helpers import intent
import homeassistant.config as conf_util
from homeassistant.helpers import template
from homeassistant.helpers.network import get_url

from .xiaoai_view import XiaoaiGateView
from .util import VERSION, DOMAIN, DATA_AGENT, DATA_CONFIG, ApiConfig, find_entity, trim_char, \
    matcher_brightness, matcher_color, matcher_script, matcher_watch_tv, \
    matcher_automation, matcher_query_state, matcher_switch

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
        local = hass.config.path("custom_components/conversation/local")
        hass.http.register_static_path('/conversation', local, False)
        hass.http.register_view(XiaoaiGateView)

    # 解析模板
    def template(self, message):
        tpl = template.Template(message, self.hass)
        return tpl.async_render(None)

    # 返回意图结果
    def intent_result(self, message):
        intent_result = intent.IntentResponse()
        intent_result.async_set_speech(message)
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

        # 看电视
        intent_result = await self.execute_watch_tv(_text)
        if intent_result is not None:
            return intent_result

        # 查询设备状态
        intent_result = await self.execute_query_state(_text)
        if intent_result is not None:
            return intent_result
        
        # 灯光颜色控制
        intent_result = await self.execute_light_color(_text)
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
        # 去掉前后标点符号
        _text = trim_char(text)
        # 发送事件，共享给其他组件
        text_data = { 'text': _text }
        hass.bus.fire('ha_voice_text_event', text_data)
        # 调用python_script.conversation
        if hass.services.has_service('python_script', 'conversation'):
            hass.async_create_task(hass.services.async_call('python_script', 'conversation', text_data))
        return _text

    # 查看设备
    def query_device(self, text):
        hass = self.hass
        device_type = None
        if text == '查看全部设备':
            device_type = ''
        elif text == '查看全部灯':
            device_type = '.light'
        elif text == '查看全部传感器':
            device_type = '.sensor'
        elif text == '查看全部开关':
            device_type = '.switch'
        elif text == '查看全部脚本':
            device_type = '.script'
        elif text == '查看全部自动化':
            device_type = '.automation'
        elif text == '查看全部场景':
            device_type = '.scene'

        if device_type is not None:
            return self.intent_result(self.template('''
                <table border cellpadding="5" style="border-collapse: collapse;">
                    <tr><th>名称</th><th>状态</th><th>操作</th></tr>
                    {% for state in states''' + device_type + ''' -%}
                    <tr>
                        <td>{{state.attributes.friendly_name}}</td>
                        <td>{{state.state}}</td>                        
                        <td>
                            {% if 'light.' in state.entity_id or 
                                  'switch.' in state.entity_id or
                                  'script.' in state.entity_id or
                                  'automation.' in state.entity_id or
                                  'scene.' in state.entity_id -%}
                                <a onclick="triggerDevice('{{state.entity_id}}', '正在执行', `{{state.attributes.friendly_name}}`)" style="color:#03a9f4;">触发</a>
                            {%- else -%}
                 
                            {%- endif %}
                        </td>
                    </tr>
                    {%- endfor %}
                </table>
            '''))
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
                    _LOGGER.info('执行脚本：' + entity_id)
                    await hass.services.async_call(arr[0], arr[1])
                    return self.intent_result("正在执行自定义脚本：" + entity_id)
            # 查询设备状态
            if friendly_name is not None:
                friendly_name_lower = friendly_name.lower()
                if text.lower() == friendly_name_lower + '的状态':
                    return self.intent_result(friendly_name + '的状态：' + state.state)
                # 查询设备属性
                if text.lower() == friendly_name_lower + '的属性':
                    message = self.template('''
                    {% set entity_id = "''' + entity_id + '''" -%}
                    <table border cellpadding="5" style="border-collapse: collapse;">
                        <tr>
                            <th>{{entity_id}}</th>
                            <th>{{states(entity_id)}}</th>
                        </tr>
                        {% for state in states[entity_id].attributes -%}
                        <tr>
                            <td>{{state}}</td>
                            <td>{{states[entity_id].attributes[state]}}</td>
                        </tr>  
                        {%- endfor %}
                    </table>
                    ''')
                    return self.intent_result(message)
                # 查询摄像监控画面
                if text.lower() == '查看' + friendly_name_lower + '的画面':
                    return self.intent_result(self.template('''
                    {% set image = states['camera.generic_camera'].attributes['entity_picture'] %}
                    <a href="{{ image }}" target="_blank">  <img src="{{ image }}" style="max-width:100%;" /> </a>
                    '''))

        return None
    
    # 执行灯光调色
    async def execute_light_color(self, text):
        result = matcher_color(text)
        if result is not None:
            state = find_entity(self.hass, result[0], 'light')
            if state is not None:
                self.call_service('light.turn_on', {
                    'entity_id': state.entity_id,
                    'color_name': result[1]
                })
                return self.intent_result(f"已经设置为{result[2]}色")
    
    # 执行灯光亮度
    async def execute_light_brightness(self, text):
        result = matcher_brightness(text)
        if result is not None:
            state = find_entity(self.hass, result[0], 'light')
            if state is not None:
                self.call_service('light.turn_on', {
                    'entity_id': state.entity_id,
                    'brightness_pct': result[1]
                })
                return self.intent_result(f"亮度已经设置为{result[1]}%")
    # 执行脚本
    async def execute_script(self, text):
        result = matcher_script(text)
        if result is not None:
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
                        self.call_service(entity_id)
                        return self.intent_result("正在执行自定义脚本：" + entity_id)

    # (执行|触发|打开|关闭)自动化
    async def execute_automation(self, text):
        result = matcher_automation(text)
        if result is not None:
            action = result[0]
            state = find_entity(self.hass, result[1], 'automation')
            if state is not None:
                service_data = {'entity_id': state.entity_id}
                if action == '执行' or action == '触发':
                    self.call_service('automation.trigger', service_data)
                    return self.intent_result("正在触发自动化：" + entity_id)
                elif action == '打开':
                    self.call_service('automation.turn_on', service_data)
                    return self.intent_result("正在打开自动化：" + entity_id)
                elif action == '关闭':
                    self.call_service('automation.turn_off', service_data)
                    return self.intent_result("正在关闭自动化：" + entity_id)

    # 查看设备状态
    async def execute_query_state(self, text):
        result = matcher_query_state(text)
        if result is not None:
            state = find_entity(self.hass, result[0])
            if state is not None:
                attributes = state.attributes
                friendly_name = attributes.get('friendly_name')
                return self.intent_result(f"{friendly_name}的状态是：{state.state}")

    # 看电视
    async def execute_watch_tv(self, text):
        result = matcher_watch_tv(text)
        if result is not None:
            cfg = self.api_config.get_config()
            entity_id = cfg.get('media_player')
            if self.hass.states.get(entity_id) is not None:
                self.call_service('media_player.play_media', {
                    'entity_id': entity_id,
                    'media_content_id': result,
                    'media_content_type': 'video'
                })
                return self.intent_result(f"正在{text}，请查看是否成功")

    # 执行开关
    async def execute_switch(self, _text):
        hass = self.hass
        result = matcher_switch(_text)
        if result is not None:                
            _name = result[0]
            service_type = result[1]
            intent_type = result[2]
            # 操作所有灯和开关
            if _name == '所有灯' or _name == '所有的灯' or _name == '全部灯' or _name == '全部的灯':
                self.call_service(f'light.{service_type}', {
                    'entity_id': self.template('{% for state in states.light -%}{{ state.entity_id }},{%- endfor %}').strip(',')
                })
                return self.intent_result("正在" + _text + self.template('''
                    <hr />
                    <table border cellpadding="5" style="border-collapse: collapse;">
                        <tr><th>名称</th><th>状态</th></tr>
                        {% for state in states.light -%}
                        <tr>
                            <td>{{state.attributes.friendly_name}}</td>
                            <td>{{state.state}}</td>  
                        </tr>
                        {%- endfor %}
                    </table>
                '''))
            elif _name == '所有开关' or _name == '所有的开关' or _name == '全部开关' or _name == '全部的开关':
                self.call_service(f'switch.{service_type}', {
                    'entity_id': self.template('{% for state in states.switch -%}{{ state.entity_id }},{%- endfor %}').strip(',')
                })
                self.call_service(f'input_boolean.{service_type}', {
                    'entity_id': self.template('{% for state in states.input_boolean -%}{{ state.entity_id }},{%- endfor %}').strip(',')
                })
                return self.intent_result("正在" + _text + self.template('''
                    <hr />
                    <table border cellpadding="5" style="border-collapse: collapse;">
                        <tr><th>名称</th><th>状态</th></tr>
                        {% for state in states.switch -%}
                        <tr>
                            <td>{{state.attributes.friendly_name}}</td>
                            <td>{{state.state}}</td>  
                        </tr>
                        {%- endfor %}
                        {% for state in states.input_boolean -%}
                        <tr>
                            <td>{{state.attributes.friendly_name}}</td>
                            <td>{{state.state}}</td>  
                        </tr>
                        {%- endfor %}
                    </table>
                '''))
            else:
                # 当名称包含多个设备时执行
                result = self.matcher_multiple_switch(_name, service_type)
                if result is not None:
                    return self.intent_result("正在执行" + result)
                # 如果没有这个设备，则返回为空
                state = find_entity(self.hass, _name, ['input_boolean', 'light', 'switch'])
                if state is not None:
                    await intent.async_handle(hass, DOMAIN, intent_type, {'name': {'value': _name}})
                    return self.intent_result("正在" + _text)

    # 执行多个开关
    def matcher_multiple_switch(self, text, service_type):
        if text.count('灯') > 1:
            matchObj = re.findall(r'((.*?)灯)', text)
            _list = []
            for item in matchObj:
                # 这里去掉常用连接汉字
                _name = trim_char(item[0].strip('和跟'))
                print(_name)
                state = find_entity(self.hass, _name, ['input_boolean', 'light', 'switch'])
                if state is not None:
                    print(state.domain)
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
                _LOGGER.info(res)
                message = res['data']['info']['text']
        except Exception as e:
            _LOGGER.info(e)        
        return message

    # 配置设置
    async def setting(self, service):
        hass = self.hass
        is_save = False
        config_data = {}
        data = service.data
        media_player_entity_id = data.get('media_player', '')
        if media_player_entity_id != '':
            if hass.states.get(media_player_entity_id) is not None:
                # 保存媒体播放器
                config_data.update({'media_player': media_player_entity_id})
                is_save = True
            else:
                self.call_service('persistent_notification.create', {
                    'message': '选择的媒体播放器在系统中不存在',
                    'title': '语音小助手',
                    'notification_id': 'conversation-error'
                })
        # 保存配置
        if is_save:
            self.api_config.save_config(config_data)
            self.call_service('persistent_notification.create', {
                    'message': '配置信息保存成功',
                    'title': '语音小助手',
                    'notification_id': 'conversation-success'
                })

    # 记录语音识别语句
    async def set_state(self, text=VERSION, source = '', timestamp = ''):
        hass = self.hass
        try:
            base_url = get_url(hass)
        except Exception as ex:
            base_url = 'http://localhost:8123'
        hass.states.async_set('conversation.voice', text, {
            "icon": "mdi:account-voice",
            "friendly_name": "语音助手",
            "timestamp": timestamp,
            "source": source,
            "version": VERSION,
            'link': base_url + '/conversation/index.html?ver=' + VERSION,
            'XiaoAi': base_url + '/conversation-xiaoai',
            'github': 'https://github.com/shaonianzhentan/conversation'
        })