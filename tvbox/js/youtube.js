// YouTube 本地 drpy2 規則 — 取代失效的 csp_Youtube
// 清單/搜尋走 WEB InnerTube(videoRenderer)，播放走 IOS HLS(全畫質) + ANDROID itag18 後備
var WEB_KEY = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8';
var WEB_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';
var IOS_UA = 'com.google.ios.youtube/21.03.4 (iPhone16,2; U; CPU iOS 18_0 like Mac OS X)';
var AND_UA = 'com.google.android.youtube/21.03.36 (Linux; U; Android 15; GB) gzip';

var rule = {
	title: 'YouTube',
	host: 'https://www.youtube.com',
	timeout: 8000,
	play_parse: true,
	play_json: [],
	searchable: 1,
	quickSearch: 0,
	filterable: 0,
	class_name: 'HDR&音樂&綜藝&紀錄片&演示片&短劇&劇集&電影&體育&時尚潮流&放鬆&4K&科普知識&科技&解說&神秘&動畫片',
	class_url: 'HDR&华语音乐&综艺&纪录片&演示片 4K&短劇&电视剧&电影&體育&时尚穿搭&放松音乐&4K&宇宙科普&科技&影视解說&神秘事件&动画片',
	homeUrl: '/',
	url: 'fyclass',
	detailUrl: '',
	searchUrl: 'youtube',
	搜索: '*',

	一级: `js:
var YT_WEB_KEY = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8';
var YT_WEB_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';
var key = (typeof KEY !== 'undefined' && KEY) ? KEY : (typeof MY_CATE !== 'undefined' ? MY_CATE : '');
key = ('' + key).trim();
var pg = (typeof MY_PAGE !== 'undefined' && MY_PAGE) ? MY_PAGE : 1;
if (!rule.__tok) rule.__tok = {};
var token = rule.__tok[key] || '';
var body;
if (pg > 1 && token) {
	body = { context: { client: { clientName: 'WEB', clientVersion: '2.20240620.00.00', hl: 'zh-TW', gl: 'TW' } }, continuation: token };
} else {
	body = { context: { client: { clientName: 'WEB', clientVersion: '2.20240620.00.00', hl: 'zh-TW', gl: 'TW' } }, query: key };
}
var vods = [];
var seen = {};
function ytLog(msg) { try { log('youtube 一级 ' + msg); } catch (e) {} }
function ytTitle(t) {
	if (!t) return '';
	if (t.simpleText) return t.simpleText;
	if (t.runs && t.runs.length) return t.runs.map(function (r) { return r.text || ''; }).join('');
	return '';
}
function ytAdd(v) {
	if (!v || !v.videoId || seen[v.videoId]) return;
	var title = ytTitle(v.title);
	if (!title) return;
	var thumbs = (v.thumbnail && v.thumbnail.thumbnails) || [];
	var pic = thumbs.length ? thumbs[thumbs.length - 1].url : 'https://i.ytimg.com/vi/' + v.videoId + '/hqdefault.jpg';
	var len = (v.lengthText && (v.lengthText.simpleText || ytTitle(v.lengthText))) || '';
	seen[v.videoId] = true;
	vods.push({ vod_id: v.videoId, vod_name: title, vod_pic: pic, vod_remarks: len });
}
function ytWalk(o) {
	if (!o || typeof o !== 'object') return;
	if (o.videoRenderer) ytAdd(o.videoRenderer);
	for (var k in o) ytWalk(o[k]);
}
function ytFindToken(o) {
	if (!o || typeof o !== 'object') return '';
	if (o.continuationCommand && o.continuationCommand.token) return o.continuationCommand.token;
	for (var k in o) { var t = ytFindToken(o[k]); if (t) return t; }
	return '';
}
function ytExtractJson(html, marker) {
	var pos = html.indexOf(marker);
	if (pos < 0) return '';
	var start = html.indexOf('{', pos);
	if (start < 0) return '';
	var depth = 0, inStr = false, esc = false;
	for (var i = start; i < html.length; i++) {
		var ch = html.charAt(i);
		if (inStr) {
			if (esc) esc = false;
			else if (html.charCodeAt(i) === 92) esc = true;
			else if (ch === '"') inStr = false;
		} else {
			if (ch === '"') inStr = true;
			else if (ch === '{') depth++;
			else if (ch === '}') { depth--; if (depth === 0) return html.substring(start, i + 1); }
		}
	}
	return '';
}
function ytHeaders(extra) {
	var h = { 'User-Agent': YT_WEB_UA, 'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8', 'Referer': 'https://www.youtube.com/', 'Origin': 'https://www.youtube.com', 'Cookie': 'CONSENT=YES+cb.20210328-17-p0.zh-TW+FX+667' };
	for (var k in extra) h[k] = extra[k];
	return h;
}
function ytApiSearch() {
	var html = request('https://www.youtube.com/youtubei/v1/search?key=' + YT_WEB_KEY + '&prettyPrint=false', {
		method: 'POST', body: JSON.stringify(body),
		headers: ytHeaders({ 'Content-Type': 'application/json', 'X-Youtube-Client-Name': '1', 'X-Youtube-Client-Version': '2.20240620.00.00' })
	});
	var text = (html || '').trim();
	if (!text || (text.charAt(0) !== '{' && text.charAt(0) !== '[')) throw new Error('api non-json len=' + text.length);
	var json = JSON.parse(text);
	ytWalk(json);
	rule.__tok[key] = ytFindToken(json);
}
function ytPageSearch() {
	if (pg > 1) return;
	var html = request('https://www.youtube.com/results?search_query=' + encodeURIComponent(key) + '&hl=zh-TW&gl=TW&persist_app=1&app=desktop', { headers: ytHeaders({}) });
	var text = ytExtractJson(html || '', 'ytInitialData');
	if (!text) throw new Error('page no ytInitialData len=' + (html || '').length);
	ytWalk(JSON.parse(text));
}
try { ytApiSearch(); } catch (e) { ytLog('api error: ' + e.message); }
if (!vods.length) { try { ytPageSearch(); } catch (e2) { ytLog('page error: ' + e2.message); } }
VODS = vods;`,

	二级: `js:
var vid = (typeof detailUrl !== 'undefined' && detailUrl) ? detailUrl : input;
if (vid && vid.indexOf('@@') !== -1) vid = vid.split('@@')[0];
var pic = 'https://i.ytimg.com/vi/' + vid + '/hqdefault.jpg';
VOD = { vod_id: vid, vod_name: 'YouTube ' + vid, vod_pic: pic, vod_content: '', vod_play_from: 'YouTube', vod_play_url: '播放$https://www.youtube.com/watch?v=' + vid };`,

	lazy: `js:
var YT_WEB_KEY = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8';
var YT_IOS_UA = 'com.google.ios.youtube/21.03.4 (iPhone16,2; U; CPU iOS 18_0 like Mac OS X)';
var YT_AND_UA = 'com.google.android.youtube/21.03.36 (Linux; U; Android 15; GB) gzip';
function ytVideoId(raw) {
	var s = (raw || '') + '';
	if (s.indexOf('$') !== -1) s = s.split('$').pop();
	var m = s.match(/[?&]v=([A-Za-z0-9_-]{11})/);
	if (m) return m[1];
	m = s.match(/youtu\.be\/([A-Za-z0-9_-]{11})/);
	if (m) return m[1];
	m = s.match(/^([A-Za-z0-9_-]{11})$/);
	return m ? m[1] : s;
}
var vid = ytVideoId(input);
function ytPlayer(client, ver, ua) {
	var body = { context: { client: { clientName: client, clientVersion: ver, hl: 'zh-TW', gl: 'TW' } }, videoId: vid, contentCheckOk: true, racyCheckOk: true };
	try {
		var html = request('https://www.youtube.com/youtubei/v1/player?key=' + YT_WEB_KEY + '&prettyPrint=false', {
			method: 'POST', body: JSON.stringify(body),
			headers: { 'Content-Type': 'application/json', 'User-Agent': ua, 'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8', 'Origin': 'https://www.youtube.com', 'Referer': 'https://www.youtube.com/' }
		});
		return JSON.parse(html);
	} catch (e) { try { log('youtube lazy ' + client + ' error: ' + e.message); } catch (ee) {} return null; }
}
var url = '';
var ua = YT_AND_UA;
var and = ytPlayer('ANDROID', '21.03.36', YT_AND_UA);
if (and && and.streamingData) {
	var sd = and.streamingData;
	var fmts = (sd.formats || []).filter(function (f) { return f.url && f.mimeType && f.mimeType.indexOf('video/') === 0; });
	fmts.sort(function (a, b) { return (b.height || 0) - (a.height || 0); });
	if (fmts.length) url = fmts[0].url;
}
if (!url) {
	var ios = ytPlayer('IOS', '21.03.4', YT_IOS_UA);
	if (ios && ios.streamingData && ios.streamingData.hlsManifestUrl) { url = ios.streamingData.hlsManifestUrl; ua = YT_IOS_UA; }
}
if (url) { input = { parse: 0, jx: 0, url: url, header: { 'User-Agent': ua, 'Referer': 'https://www.youtube.com/' } }; } else { input = ''; }`,
};

function init(ext) {}
