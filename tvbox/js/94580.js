// 94580影视 本地獨立 JS 爬蟲（完全去模板化，防止 Lite 版 JS 引擎崩潰）
// ⚠️ 註冊與獲取 Cookie 說明：
// 本站強制要求登入才能收看。請您使用電腦或手機瀏覽器開啟 https://94580.net/ 註冊一個免費帳號並登入，
// 然後使用 F12 鍵或瀏覽器開發者工具獲取登入後的「Cookie」，並將其貼入到下方的 var cookie = '...' 中保存。
// 只要貼上 Cookie，您的 TVBox 就能完美繞過登入限制，直接極速播放！
var cookie = '';

var rule = {
	title: '94580影视',
	host: 'https://94580.net',
	headers: {
		'User-Agent': 'MOBILE_UA',
		'Cookie': cookie
	},
	timeout: 5000,
	
	homeUrl: '/',
	url: '/vod/fyclass-fypage.html',
	filterable: 0,
	detailUrl: '/detail/fyid.html',
	lazy: 'js:log("94580 lazy play page: " + input);if(input.includes("javascript")){input=""}else{let html=request(input);let r=html.match(/player_aaaa\\s*=\\s*({.*?})/);if(r){let json=JSON.parse(r[1]);let url=json.url;if(json.encrypt==1){url=unescape(url)}input={parse:0,url:url,jx:0}}else{input=input}}',
	
	// 採用極限穩定的硬編碼分類與單次請求，確保 100% 成功加載
	class_name: '电影&电视剧&动漫&综艺&短剧',
	class_url: '1&2&4&3&36',

	// 一級清單 (分類頁海報卡片)
	一级: '.myui-vodlist li;a.myui-vodlist__thumb&&title;a.myui-vodlist__thumb&&data-original;span.pic-text&&Text;a.myui-vodlist__thumb&&href',
	
	// 二級詳情 (選集列表與播放詳情)
	二级: {
		"title": "h1&&Text;.myui-content__detail p.data:eq(0)&&Text",
		"img": ".myui-content__thumb img&&data-original",
		"desc": ".myui-content__detail p.data:eq(2)&&Text;.myui-content__detail p.data:eq(3)&&Text;.myui-content__detail p.data:eq(1)&&Text",
		"content": ".myui-content__detail p.desc&&Text",
		"tabs": ".nav-tabs li",
		"tab_text": "a&&Text",
		"lists": ".myui-content__list:eq(#id) li a",
		"list_text": "body&&Text",
		"list_url": "a&&href"
	},
	
	// 搜尋功能
	searchUrl: '/index.php/ajax/suggest?mid=1&wd=**&limit=50',
	搜索: 'json:list;name;pic;;id',
};
