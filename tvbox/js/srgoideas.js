// 台灣綜藝丨Srgoideas 本地獨立 JS 爬蟲（完全去模板化，防止 Lite 版 JS 引擎崩潰）
var rule = {
	title: '台灣綜藝丨Srgoideas',
	host: 'https://srgoideas.com',
	headers: {
		'User-Agent': 'MOBILE_UA'
	},
	timeout: 5000,
	
	homeUrl: '/',
	url: '/category/fyclass/page/fypage/',
	filterable: 0,
	detailUrl: '',
	lazy: 'js:log("srgoideas lazy input: " + input);if(input.includes("$")){input=input.split("$")[1]}let html=request(input);let r=html.match(/https?:\\/\\/[^\\\'\"\\s>\\(\\)]+\\.mp4\\?st=[^\\\'\"\\s>\\(\\)]+/i);if(r){let url=r[0].replace(/&amp;/g,"&");input={parse:0,url:url,jx:0}}else{input=input}',
	
	// 採用極限穩定的硬編碼分類，覆蓋 16 大主流台灣綜藝節目
	class_name: '小姐不熙娣&小明星大跟班&綜藝大熱門&綜藝玩很大&天才衝衝衝&飢餓遊戲&綜藝一級棒&型男大主廚&歡樂智多星&WTO姐妹會&全民星攻略&娛樂百分百&11點熱吵店&康熙來了&大學生了沒&國光幫幫忙',
	class_url: 'variety-show/%e5%b0%8f%e5%a7%90%e4%b8%8d%e7%86%99%e5%a8%a3&variety-show/%e5%b0%8f%e6%98%8e%e6%98%9f%e5%a4%a7%e8%b7%9f%e7%8f%ad&variety-show/%e7%b6%9c%e8%97%9d%e5%a4%a7%e7%86%b1%e9%96%80&variety-show/%e7%b6%9c%e8%97%9d%e7%8e%a9%e5%be%88%e5%a4%a7&variety-show/tian-cai-chong-chong-chong&variety-show/%e9%a3%a2%e9%a4%93%e9%81%8a%e6%88%b2&variety-show/%e7%b6%9c%e8%97%9d%e4%b8%80%e7%b4%9a%e6%a3%92&variety-show/xing-nan-da-zhu-chu&variety-show/%e6%ad%a1%e6%a8%82%e6%99%ba%e5%a4%9a%e6%98%9f&variety-show/wto&variety-show/%e5%85%a8%e6%b0%91%e6%98%9f%e6%94%bb%e7%95%a5&variety-show/yu-le-bai-fen-bai&variety-show/11%e9%bb%9e%e7%86%b1%e5%90%b5%e5%ba%97&variety-show/kang-xi-lai-le&variety-show/da-xue-sheng-le-mei&variety-show/guo-guang-bang-bang-mang',

	// 一級清單 (分類頁文章列表，必須為分號分割字串以相容 split)
	一级: 'article.hentry;.entry-title a&&Text;;;.entry-title a&&href',
	
	// 二級詳情 (自定義 JS 動態生成多分部 Part 1, Part 2, Part 3 列表)
	二级: {
		"title": "h1.entry-title&&Text",
		"img": "",
		"desc": ".entry-header .entry-meta&&Text",
		"content": ".entry-content&&Text",
		"tabs": "js:TABS=['直連播放']",
		"lists": 'js:log("srgoideas detail input: " + input);if(input.includes("$")){input=input.split("$")[1]}let html=request(input);let urls=[];let parts=pdfa(html,"ul.contentlist li");if(parts.length>0){parts.forEach((p,idx)=>{let text=pdfh(p,"body&&Text");if(text.toLowerCase().includes("full") || text.includes("一起播放") || text.includes("整期")){return}let href=pd(p,"a&&href",input);if(!href){href=input}urls.push(text+"$"+href)})}else{urls.push("單一分部$"+input)}LISTS=[urls];'
	},
	
	// 搜尋功能
	searchUrl: '/page/fypage/?s=**',
	搜索: 'article.hentry;.entry-title a&&Text;;;.entry-title a&&href',
};
