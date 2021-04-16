import{d as t,c as e,r as a,o as s,w as n,a as i,t as l,b as o,e as r,F as d,f as c,B as u,A as h,E as m,l as p,g,h as f,i as y,j as _,k as v,m as w,n as b}from"./vendor.2bd3f3a3.js";!function(t=".",e="__import__"){try{self[e]=new Function("u","return import(u)")}catch(a){const s=new URL(t,location),n=t=>{URL.revokeObjectURL(t.src),t.remove()};self[e]=t=>new Promise(((a,i)=>{const l=new URL(t,s);if(self[e].moduleMap[l])return a(self[e].moduleMap[l]);const o=new Blob([`import * as m from '${l}';`,`${e}.moduleMap['${l}']=m;`],{type:"text/javascript"}),r=Object.assign(document.createElement("script"),{type:"module",src:URL.createObjectURL(o),onerror(){i(new Error(`Failed to import: ${t}`)),n(r)},onload(){a(self[e].moduleMap[l]),n(r)}});document.head.appendChild(r)})),self[e].moduleMap={}}}("assets/");const k=t({props:{data:{type:Object,default:()=>({cmd:"",text:""})}}}),x=i("a",null,"HomeAssistant",-1);k.render=function(t,o,r,d,c,u){const h=a("a-avatar"),m=a("a-comment"),p=a("a-card");return s(),e(p,{size:"small",title:t.data.cmd},{default:n((()=>[i(m,null,{author:n((()=>[x])),avatar:n((()=>[i(h,{src:"https://www.home-assistant.io/images/home-assistant-logo.svg",alt:"HomeAssistant"})])),content:n((()=>[i("p",null,l(t.data.text),1)])),_:1})])),_:1},8,["title"])};var M=t({props:{data:Object}});const O=o("第一集"),C=o("第二集"),j=o("第一集"),S=o("第一集"),U=o("第一集"),V=o("第一集"),$=o("第一集"),L=o("第一集");M.render=function(t,l,o,r,d,c){const u=a("a-card-grid"),h=a("a-card");return s(),e(h,{title:"我想看司藤",size:"small"},{default:n((()=>[i(h,{title:"获取所有状态值"},{default:n((()=>[i(u,{style:{width:"25%","text-align":"center"}},{default:n((()=>[O])),_:1}),i(u,{style:{width:"25%","text-align":"center"}},{default:n((()=>[C])),_:1}),i(u,{style:{width:"25%","text-align":"center"}},{default:n((()=>[j])),_:1}),i(u,{style:{width:"25%","text-align":"center"}},{default:n((()=>[S])),_:1}),i(u,{style:{width:"25%","text-align":"center"}},{default:n((()=>[U])),_:1}),i(u,{style:{width:"25%","text-align":"center"}},{default:n((()=>[V])),_:1}),i(u,{style:{width:"25%","text-align":"center"}},{default:n((()=>[$])),_:1}),i(u,{style:{width:"25%","text-align":"center"}},{default:n((()=>[L])),_:1})])),_:1})])),_:1})};var A=t({props:{data:{type:Object,default:()=>({cmd:"",text:"",list:[]})}},setup:()=>({checked:r(!1)})});A.render=function(t,r,u,h,m,p){const g=a("a-list-item"),f=a("a-list"),y=a("a-card");return s(),e(y,{title:t.data.cmd},{default:n((()=>[i(f,{bordered:""},{default:n((()=>[(s(!0),e(d,null,c(t.data.list,((t,a)=>(s(),e(g,{key:a},{actions:n((()=>[o(l(t.value),1)])),default:n((()=>[o(l(t.name)+" ",1)])),_:2},1024)))),128))])),_:1})])),_:1},8,["title"])};var R=t({components:{BarsOutlined:u,AudioOutlined:h,EditOutlined:m,CardMessage:k,CardVideo:M,CardState:A},setup:()=>({hass:null,list:r([]),isVoice:r(!1)}),data(){return{msg:"",throttle:p.throttle((()=>{this.sendMsg(this.msg)}),2e3,{leading:!1,trailing:!0})}},created(){this.connect()},methods:{async connect(){let t;try{t=await g({loadTokens(){try{return JSON.parse(localStorage.hassTokens)}catch(t){}},saveTokens:t=>{localStorage.hassTokens=JSON.stringify(t)}})}catch(a){if(a!==f)return void alert(`Unknown error: ${a}`);{const e=prompt("请输入要连接的HomeAssistant地址?",location.origin);t=await g({hassUrl:e})}}const e=await y({auth:t});location.search.includes("auth_callback=1")&&history.replaceState(null,"",location.pathname),this.hass=e,_(e).then((t=>{console.log("Logged in as",t),e.sendMessagePromise({type:"get_states"}).then((e=>{let a=e.find((t=>"conversation.voice"===t.entity_id)),s=new URLSearchParams(location.search),n=a.attributes.version;s.get("ver")!=n?location.search=`?ver=${n}`:this.list.push({name:"CardMessage",data:{cmd:"HomeAssistant服务连接成功",text:`【${t.name}】你好，欢迎使用语音小助手`}})}))}))},sendMsgKeydown(t){const{msg:e,isVoice:a}=this;if(e)return a?this.throttle():void(13===t.keyCode&&this.sendMsg(e))},sendMsg(t){this.msg="",this.hass.sendMessagePromise({conversation_id:`${Math.random().toString(16).substr(2,10)}${Math.random().toString(16).substr(2,10)}`,text:t,type:"conversation/process"}).then((({speech:e})=>{const a=e.plain.extra_data,s={cmd:t,text:e.plain.speech,list:[]};a?this.hass.sendMessagePromise({type:"get_states"}).then((t=>{const e=t.filter((t=>a.data.includes(t.entity_id)));if(1===e.length){const{attributes:t,state:a}=e[0];s.list=Object.keys(t).map((e=>({name:e,value:t[e]}))),s.list.unshift({name:"状态",value:a})}else s.list=e.map((t=>({name:t.attributes.friendly_name,value:t.state})));console.log(s),this.list.push({name:"CardState",data:s})})):this.list.push({name:"CardMessage",data:s})}))},toggleVoiceClick(){this.isVoice=!this.isVoice}}});const E={style:{position:"fixed",bottom:"0",left:"0",width:"100%",padding:"10px",background:"white"}};R.render=function(t,l,o,r,u,h){const m=a("BarsOutlined"),p=a("AudioOutlined"),g=a("EditOutlined"),f=a("a-tooltip"),y=a("a-input");return s(),e(d,null,[(s(!0),e(d,null,c(t.list,((t,a)=>(s(),e(v(t.name),{key:a,data:t.data},null,8,["data"])))),128)),i("div",E,[i(y,{placeholder:"请输入文字命令",value:t.msg,"onUpdate:value":l[2]||(l[2]=e=>t.msg=e),onKeydown:l[3]||(l[3]=e=>t.sendMsgKeydown(e))},{prefix:n((()=>[i(m,{type:"user"})])),suffix:n((()=>[i(f,{title:t.isVoice?"自动发送":"手动发送"},{default:n((()=>[i("span",{onClick:l[1]||(l[1]=(...e)=>t.toggleVoiceClick&&t.toggleVoiceClick(...e))},[t.isVoice?(s(),e(p,{key:0,style:{color:"rgba(0, 0, 0, 0.45)"}})):(s(),e(g,{key:1,style:{color:"rgba(0, 0, 0, 0.45)"}}))])])),_:1},8,["title"])])),_:1},8,["value"])])],64)};w(R).use(b).mount("#app");
