// FongMi TV (影視TV) 原生 QuickJS 爬蟲 — YouTube（極致畫質無死角修復版）
// 1. 修復影片詳情與播放標題（不再顯示英文亂碼 ID）
// 2. 突破 720p 限制，完整解鎖 4K (2160p60 HDR) / 2K (1440p) / 1080p60 全畫質切換選單
// 3. 完美支援 YouTube 新聞與各類即時直播（Live Stream）
// 4. 點播支援動態 DASH 串流與直鏈 MP4 多重備援，徹底杜絕「播放網址載入失敗」
import { Spider } from 'catvod';

const WEB_KEY = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8';
const WEB_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36';
const IOS_UA = 'com.google.ios.youtube/21.03.4 (iPhone16,2; U; CPU iOS 18_1 like Mac OS X)';
const AND_UA = 'com.google.android.youtube/21.03.36 (Linux; U; Android 15; GB) gzip';

const CLASSES = [
    { type_id: '台灣新聞直播', type_name: '🔴新聞直播' },
    { type_id: '4K 60fps HDR', type_name: '4K演示' },
    { type_id: '熱門推薦', type_name: '熱門' },
    { type_id: '華語流行音樂', type_name: '音樂' },
    { type_id: '熱門綜藝節目', type_name: '綜藝' },
    { type_id: '完整電影', type_name: '電影' },
    { type_id: '熱門連續劇', type_name: '電視劇' },
    { type_id: '熱門短劇', type_name: '短劇' },
    { type_id: '體育精華', type_name: '體育' },
    { type_id: '科技數碼評測', type_name: '科技' },
    { type_id: '放鬆輕音樂', type_name: '放鬆' },
    { type_id: '熱門動漫', type_name: '動畫' }
];

export default class YouTubeSpider extends Spider {
    constructor() {
        super();
        this.__tokens = {};
        this.__vodCache = new Map();
        this.__mpdCache = new Map();
    }

    async init(extend) {
    }

    async homeContent(filter) {
        return {
            class: CLASSES
        };
    }

    async homeVideoContent() {
        return await this.categoryContent('4K 60fps HDR', '1', false, {});
    }

    async categoryContent(tid, pg, filter, extend) {
        return await this.searchContent(tid, false, pg);
    }

    async detailContent(ids) {
        const vid = this.extractId((ids || [])[0]);
        if (!vid) return { list: [] };

        // 1. 先從記憶體快取中讀取真實標題與封面
        let cached = this.__vodCache.get(vid);
        let title = cached ? cached.vod_name : '';
        let pic = cached ? cached.vod_pic : `https://i.ytimg.com/vi/${vid}/hqdefault.jpg`;
        let remarks = cached ? cached.vod_remarks : '';
        let desc = cached ? cached.vod_content : '';

        // 2. 若快取未命中（如外部跳轉），請求 YouTube API 獲取真實影片資訊
        if (!title) {
            try {
                const info = await this.fetchPlayer(vid, 'IOS', '21.03.4', IOS_UA);
                if (info?.videoDetails) {
                    const vd = info.videoDetails;
                    title = vd.title || ('YouTube ' + vid);
                    remarks = vd.author ? `頻道：${vd.author}` : '';
                    desc = vd.shortDescription || '';
                    if (vd.thumbnail?.thumbnails?.length) {
                        pic = vd.thumbnail.thumbnails[vd.thumbnail.thumbnails.length - 1].url;
                    }
                    this.__vodCache.set(vid, { vod_name: title, vod_pic: pic, vod_remarks: remarks, vod_content: desc });
                }
            } catch (e) {
                this.log('detailContent fetch error: ' + (e?.message || e));
            }
        }

        const vod = {
            vod_id: vid,
            vod_name: title || ('YouTube ' + vid),
            vod_pic: pic,
            vod_remarks: remarks,
            vod_content: desc,
            vod_play_from: 'YouTube',
            vod_play_url: `播放$https://www.youtube.com/watch?v=${vid}`
        };

        return { list: [vod] };
    }

    async searchContent(key, quick, pg = '1') {
        key = String(key || '').trim();
        if (!key) key = '4K 60fps HDR';
        const pageNum = parseInt(pg) || 1;
        const token = this.__tokens[key] || '';

        let body;
        if (pageNum > 1 && token) {
            body = {
                context: { client: { clientName: 'WEB', clientVersion: '2.20240901.00.00', hl: 'zh-TW', gl: 'TW' } },
                continuation: token
            };
        } else {
            body = {
                context: { client: { clientName: 'WEB', clientVersion: '2.20240901.00.00', hl: 'zh-TW', gl: 'TW' } },
                query: key
            };
        }

        const vods = [];
        const seen = {};

        try {
            const data = await this.net.json(`https://www.youtube.com/youtubei/v1/search?key=${WEB_KEY}&prettyPrint=false`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'User-Agent': WEB_UA,
                    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
                    'Origin': 'https://www.youtube.com',
                    'Referer': 'https://www.youtube.com/',
                    'X-Youtube-Client-Name': '1',
                    'X-Youtube-Client-Version': '2.20240901.00.00'
                },
                body: JSON.stringify(body)
            });
            this.walkVideos(data, vods, seen);
            this.__tokens[key] = this.findToken(data);
        } catch (e) {
            this.log('YouTube API search error: ' + (e?.message || e));
        }

        // Web 備援（僅首頁失敗時嘗試）
        if (!vods.length && pageNum === 1) {
            try {
                const res = await this.net.req(`https://www.youtube.com/results?search_query=${encodeURIComponent(key)}&hl=zh-TW&gl=TW&persist_app=1&app=desktop`, {
                    headers: {
                        'User-Agent': WEB_UA,
                        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
                        'Referer': 'https://www.youtube.com/'
                    }
                });
                const html = res?.content || '';
                const jsonText = this.extractInitialData(html);
                if (jsonText) {
                    const pageData = JSON.parse(jsonText);
                    this.walkVideos(pageData, vods, seen);
                }
            } catch (e) {
                this.log('YouTube Web search error: ' + (e?.message || e));
            }
        }

        return {
            list: vods,
            page: pageNum,
            pagecount: 99,
            limit: 20,
            total: 999
        };
    }

    async playerContent(flag, id, vipFlags) {
        const vid = this.extractId(id);
        let playUrl = '';
        let playFormat = '';
        let playHeader = { 'User-Agent': IOS_UA, 'Referer': 'https://www.youtube.com/' };

        let iosData = null;
        let andData = null;

        // 1. 請求高規格 IOS 客戶端數據（攜帶 Retina 4K 螢幕資訊，完整解鎖 4K/2K/1080p）
        try {
            iosData = await this.fetchPlayer(vid, 'IOS', '21.03.4', IOS_UA);
        } catch (e) {
            this.log('IOS player error: ' + (e?.message || e));
        }

        // 2. 請求 ANDROID 客戶端數據（直播流在 Android 端有完整的 HLS Master Playlist）
        try {
            andData = await this.fetchPlayer(vid, 'ANDROID', '21.03.36', AND_UA);
        } catch (e) {
            this.log('ANDROID player error: ' + (e?.message || e));
        }

        // A. 優先檢查是否為直播流或官方 HLS 串流 (m3u8)
        const hlsUrl = andData?.streamingData?.hlsManifestUrl || iosData?.streamingData?.hlsManifestUrl;
        if (hlsUrl) {
            playUrl = hlsUrl;
            playFormat = 'application/x-mpegURL';
            playHeader['User-Agent'] = andData?.streamingData?.hlsManifestUrl ? AND_UA : IOS_UA;
        }

        // B. 點播：使用 4K 自適應流生成動態 MPEG-DASH (.mpd) 實現全畫質（4K / 2K / 1080p / 720p / 480p）自由切換
        if (!playUrl && iosData?.streamingData?.adaptiveFormats?.length) {
            try {
                const mpd = this.buildMpd(iosData.streamingData);
                if (mpd) {
                    this.__mpdCache.set(vid, mpd);
                    playUrl = this.proxyUrl({ act: 'mpd', vid: vid });
                    playFormat = 'application/dash+xml';
                    playHeader['User-Agent'] = IOS_UA;
                }
            } catch (e) {
                this.log('buildMpd error: ' + (e?.message || e));
            }
        }

        // C. 後備方案：若 Proxy 失敗，退回直鏈 MP4 (itag 18)
        if (!playUrl && andData?.streamingData?.formats?.length) {
            const fmts = andData.streamingData.formats.filter(f => f.url && f.mimeType && f.mimeType.startsWith('video/'));
            fmts.sort((a, b) => (b.height || 0) - (a.height || 0));
            if (fmts.length) {
                playUrl = fmts[0].url;
                playFormat = 'video/mp4';
                playHeader['User-Agent'] = AND_UA;
            }
        }

        // 提取真實標題返回給播放器
        const details = iosData?.videoDetails || andData?.videoDetails;
        const title = details?.title || (this.__vodCache.get(vid)?.vod_name || ('YouTube ' + vid));
        const author = details?.author ? `頻道：${details.author}` : '';
        const pic = this.__vodCache.get(vid)?.vod_pic || `https://i.ytimg.com/vi/${vid}/hqdefault.jpg`;

        const vodUpdate = {
            vod_id: vid,
            vod_name: title,
            vod_pic: pic,
            vod_remarks: author,
            vod_content: details?.shortDescription || '',
            vod_play_from: 'YouTube',
            vod_play_url: `播放$https://www.youtube.com/watch?v=${vid}`
        };

        const result = {
            parse: 0,
            url: playUrl,
            header: playHeader,
            list: [vodUpdate]
        };

        if (playFormat) result.format = playFormat;
        return result;
    }

    async proxy(params) {
        const action = params?.act || params?.do;
        const vid = params?.vid;

        if ((action === 'mpd' || action === 'dash') && vid) {
            let mpd = this.__mpdCache.get(vid);
            if (!mpd) {
                try {
                    const info = await this.fetchPlayer(vid, 'IOS', '21.03.4', IOS_UA);
                    mpd = this.buildMpd(info?.streamingData);
                    if (mpd) this.__mpdCache.set(vid, mpd);
                } catch (e) {
                    this.log('proxy fetchPlayer error: ' + (e?.message || e));
                }
            }
            if (mpd) {
                return [
                    200,
                    'application/dash+xml',
                    mpd,
                    {
                        'Content-Type': 'application/dash+xml; charset=utf-8',
                        'Access-Control-Allow-Origin': '*',
                        'Cache-Control': 'no-cache'
                    }
                ];
            }
        }

        return [404, 'text/plain', 'Not Found'];
    }

    async fetchPlayer(vid, clientName, clientVer, ua) {
        const client = {
            clientName: clientName,
            clientVersion: clientVer,
            hl: 'zh-TW',
            gl: 'TW'
        };

        // 宣告高解析度螢幕參數，解鎖 YouTube 4K (2160p60) 與 2K (1440p60) 高畫質碼率
        if (clientName === 'IOS') {
            client.deviceMake = 'Apple';
            client.deviceModel = 'iPhone16,2';
            client.screenWidthPoints = 2796;
            client.screenHeightPoints = 1290;
            client.screenPixelDensity = 3;
            client.screenDensityFloat = 3;
            client.utcOffsetMinutes = 480;
        }

        const body = {
            context: { client: client },
            videoId: vid,
            contentCheckOk: true,
            racyCheckOk: true
        };

        return await this.net.json(`https://www.youtube.com/youtubei/v1/player?key=${WEB_KEY}&prettyPrint=false`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'User-Agent': ua,
                'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
                'Origin': 'https://www.youtube.com',
                'Referer': 'https://www.youtube.com/'
            },
            body: JSON.stringify(body)
        });
    }

    buildMpd(streamingData) {
        const ad = streamingData?.adaptiveFormats || [];
        const durationSec = Math.round((parseInt(ad[0]?.approxDurationMs || '0') / 1000)) || 3600;

        // 篩選具備 range 且有直鏈的 MP4 視訊與音訊軌（含 AV1 / AVC1 的 4K、2K、1080p）
        const videoFormats = ad.filter(f => f.url && f.mimeType && f.mimeType.startsWith('video/mp4') && f.initRange && f.indexRange);
        const audioFormats = ad.filter(f => f.url && f.mimeType && f.mimeType.startsWith('audio/mp4') && f.initRange && f.indexRange);

        if (!videoFormats.length || !audioFormats.length) return null;

        videoFormats.sort((a, b) => (b.height || 0) - (a.height || 0));

        let xml = '<?xml version="1.0" encoding="UTF-8"?>\n';
        xml += `<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" profiles="urn:mpeg:dash:profile:isoff-on-demand:2011" type="static" mediaPresentationDuration="PT${durationSec}S" minBufferTime="PT1.5S">\n`;
        xml += '  <Period>\n';

        // 視訊適應集（支援 4K (2160p)、2K (1440p)、1080p、720p 等多畫質）
        xml += '    <AdaptationSet mimeType="video/mp4" contentType="video" subsegmentAlignment="true" subsegmentStartsWithSAP="1">\n';
        for (const v of videoFormats) {
            const codecs = (v.mimeType.match(/codecs="([^"]+)"/) || [])[1] || 'avc1.640028';
            const label = v.qualityLabel || (v.height ? v.height + 'p' : 'HD');
            xml += `      <Representation id="${label}" bandwidth="${v.bitrate || 2000000}" width="${v.width || 1920}" height="${v.height || 1080}" codecs="${codecs}">\n`;
            xml += `        <BaseURL>${this.escapeXml(v.url)}</BaseURL>\n`;
            xml += `        <SegmentBase indexRange="${v.indexRange.start}-${v.indexRange.end}">\n`;
            xml += `          <Initialization range="${v.initRange.start}-${v.initRange.end}"/>\n`;
            xml += '        </SegmentBase>\n';
            xml += '      </Representation>\n';
        }
        xml += '    </AdaptationSet>\n';

        // 音訊適應集（AAC 128kbps）
        xml += '    <AdaptationSet mimeType="audio/mp4" contentType="audio" subsegmentAlignment="true" subsegmentStartsWithSAP="1">\n';
        for (const a of audioFormats) {
            const codecs = (a.mimeType.match(/codecs="([^"]+)"/) || [])[1] || 'mp4a.40.2';
            xml += `      <Representation id="audio_${a.itag}" bandwidth="${a.bitrate || 128000}" codecs="${codecs}">\n`;
            xml += `        <BaseURL>${this.escapeXml(a.url)}</BaseURL>\n`;
            xml += `        <SegmentBase indexRange="${a.indexRange.start}-${a.indexRange.end}">\n`;
            xml += `          <Initialization range="${a.initRange.start}-${a.initRange.end}"/>\n`;
            xml += '        </SegmentBase>\n';
            xml += '      </Representation>\n';
        }
        xml += '    </AdaptationSet>\n';

        xml += '  </Period>\n';
        xml += '</MPD>';
        return xml;
    }

    escapeXml(s) {
        return String(s || '').replace(/[<>&'"]/g, c => {
            switch (c) {
                case '<': return '&lt;';
                case '>': return '&gt;';
                case '&': return '&amp;';
                case '\'': return '&apos;';
                case '"': return '&quot;';
            }
        });
    }

    extractId(raw) {
        const s = String(raw || '');
        const tail = s.includes('$') ? s.split('$').pop() : s;
        const m = tail.match(/[?&]v=([A-Za-z0-9_-]{11})/);
        if (m) return m[1];
        const idx = tail.indexOf('youtu.be/');
        if (idx !== -1) return tail.substring(idx + 9, idx + 20);
        const m2 = tail.match(/^([A-Za-z0-9_-]{11})$/);
        return m2 ? m2[1] : tail;
    }

    walkVideos(o, vods, seen) {
        if (!o || typeof o !== 'object') return;
        if (o.videoRenderer) {
            const v = o.videoRenderer;
            if (v.videoId && !seen[v.videoId]) {
                const title = this.formatTitle(v.title);
                if (title) {
                    seen[v.videoId] = true;
                    const thumbs = (v.thumbnail && v.thumbnail.thumbnails) || [];
                    const pic = thumbs.length ? thumbs[thumbs.length - 1].url : `https://i.ytimg.com/vi/${v.videoId}/hqdefault.jpg`;
                    const len = (v.lengthText && (v.lengthText.simpleText || this.formatTitle(v.lengthText))) || '';
                    const vod = { vod_id: v.videoId, vod_name: title, vod_pic: pic, vod_remarks: len };
                    vods.push(vod);
                    this.__vodCache.set(v.videoId, vod);
                }
            }
        }
        for (const k in o) this.walkVideos(o[k], vods, seen);
    }

    formatTitle(t) {
        if (!t) return '';
        if (t.simpleText) return t.simpleText;
        if (t.runs && t.runs.length) return t.runs.map(r => r.text || '').join('');
        return '';
    }

    findToken(o) {
        if (!o || typeof o !== 'object') return '';
        if (o.continuationCommand && o.continuationCommand.token) return o.continuationCommand.token;
        for (const k in o) {
            const t = this.findToken(o[k]);
            if (t) return t;
        }
        return '';
    }

    extractInitialData(html) {
        const marker = 'ytInitialData';
        const pos = html.indexOf(marker);
        if (pos < 0) return '';
        const start = html.indexOf('{', pos);
        if (start < 0) return '';
        let depth = 0, inStr = false, esc = false;
        for (let i = start; i < html.length; i++) {
            const ch = html.charAt(i);
            if (inStr) {
                if (esc) esc = false;
                else if (html.charCodeAt(i) === 92) esc = true;
                else if (ch === '"') inStr = false;
            } else {
                if (ch === '"') inStr = true;
                else if (ch === '{') depth++;
                else if (ch === '}') {
                    depth--;
                    if (depth === 0) return html.substring(start, i + 1);
                }
            }
        }
        return '';
    }
}
