// Skill Translations
// 擴充字典以包含更多遊戲術語
const SKILL_TRANSLATIONS = {
    // === 自動匯入的聖物名稱翻譯 ===
    'パイトスの鍛冶工房': '派托斯的鍛造工房',
    '瘴蝕竜マグラナグラ': '瘴蝕龍馬格拉納格拉',
    'エシュリオンの生命炉': '埃修利昂的生命爐',
    '雷獣討伐奇譚': '雷獸討伐奇譚',
    '破神大戦': '破神大戰',
    '神都ロスト・マグネス': '神都失落的瑪古奈斯',
    '三皇': '三皇',
    '神隷アプロポリカ': '神隸艾普羅波利卡',
    'ソウルブレイド': '心靈之刃',
    'リラハ・エムゼル': '莉拉哈・耶姆傑爾',
    '神機『アスラトロン』': '神機《阿斯拉特隆》',
    'パンデモニウム': '潘德莫尼姆',
    '番神ユダ・ニス': '番神幽達・尼斯',
    '魔銃エーテルダイバー': '魔銃乙太潛行者',
    '破神ログシウス': '破神羅格修斯',
    '十賢臣': '十賢臣',
    'メイリー・メア': '梅莉・梅亞',
    '魔神エルド・ラヴァーナ': '魔神艾爾德・拉巴納',
    '聖戦': '聖戰',
    '氷囚のアペル・ネクシス': '冰囚的阿佩爾・尼克西斯',
    '神戒': '神戒',
    '雲神マダー・ウビス': '雲神瑪達・烏比斯',
    '魔神ミア・ルメル': '魔神米婭・盧梅爾',
    '神機メタトロン': '神機梅塔特隆',
    'リラハムル': '利拉哈姆爾',
    '番神ガーランド': '番神加蘭德',
    '魔王カルマ＝ノーグ': '魔王卡爾瑪・諾格',
    'クロノス': '克羅諾斯',
    'カイロス・ゾブラ': '卡伊洛斯・佐布拉',
    'リベレイターズ': '解放者',
    '破神封印': '破神封印',
    '氷の魔帝ゼノバス': '冰之魔帝賽諾巴斯',
    'ツクヨミ': '月讀',
    '女神四徒': '女神四徒',
    '祓獣の巫女': '祓獸的巫女',
    'スサノオ': '素戔嗚',
    '邪竜ニーズヘッグ': '邪龍尼德霍格',
    'タケミカヅチ': '建御雷',
    '神都マグネス': '神都瑪古奈斯',
    '皇竜エルド・ラヴァーナ': '皇龍艾爾德・拉巴納',
    '空中要塞ソラリス': '空中要塞索拉利斯',
    'リリー・マター': '終極莉莉',
    'ヒノカグツチ': '火之迦具土',
    'ガーディアンズ': '守衛者',
    '魔神ヴァース': '魔神瓦斯',
    'アマテラス': '天照',
    '神獣バルメイト': '神獸巴爾梅特',
    'サンドマスター': '沙漠之王',
    '英霊召喚': '英靈召喚',
    '帝国四天': '帝國四天',
    '破神ログシウス(第2形態)': '破神羅格修斯（第2形態）',
    '精霊騎士と禁書庫の大精霊｜リゼロコラボ': '精靈騎士與禁書庫的大精靈｜Re:Zero 合作',
    '聖夜のロズワール邸｜リゼロコラボ': '聖夜的羅茲瓦爾邸｜Re:Zero 合作',
    '強欲の魔女エキドナ｜リゼロコラボ': '強欲的魔女艾姬多娜｜Re:Zero 合作',
    '雪降る元日の願い': '雪落元日的祈願',
    '万福の来光': '萬福來光',
    '英霊たちのバカンス': '英靈們的假期',
    'セラフィックゲート｜ヴァルキリープロファイル −レナス−コラボ': '熾天使之門｜女神戰記 −蕾娜絲− 合作',
    'OVERLORD｜オーバーロードコラボ': 'OVERLORD｜OVERLORD 合作',
    '鮮血の戦乙女｜オーバーロードコラボ': '鮮血的女武神｜OVERLORD 合作',
    '新春の羽根つきバトル': '新春羽子板對戰',
    'VISIONS of MANA｜聖剣伝説コラボ': 'VISIONS of MANA｜聖劍傳說 合作',
    'ダモクレスの空｜コードギアスコラボ': '達摩克里斯之空｜Code Geass 合作',
    'マリン・カタストロフ': '海洋災厄',
    '星の在り処': '星之所在',
    '戦いの軌跡': '戰鬥的軌跡',
    '終焉の獣｜リゼロコラボ': '終焉之獸｜Re:Zero 合作',
    'ゼロから｜リゼロコラボ': '從零開始｜Re:Zero 合作',
    '魔界の反逆王ユリゼン｜デビルメイクライ5コラボ': '魔界的叛逆王尤里森｜惡魔獵人5 合作',
    '便利屋Devil Mey Cry｜デビルメイクライ5コラボ': '萬事屋 Devil May Cry｜惡魔獵人5 合作',
    '乙女たちの恋宴': '少女們的戀宴',
    '武力の帝国': '武力的帝國',
    '機械鎧整備士｜鋼の錬金術師コラボ': '機械鎧整備士｜鋼之鍊金術師 合作',
    'いかん、雨が降ってきたな｜鋼の錬金術師コラボ': '糟了，下雨了呢｜鋼之鍊金術師 合作',
    '約束のルベール': '約定的魯貝爾',
    'サンタガールズ': '聖誕女孩們',
    '巨人に抗いしものたち｜進撃の巨人コラボ': '對抗巨人的人們｜進擊的巨人 合作',
    'エレンVS女型の巨人｜進撃の巨人コラボ': '艾連 VS 女型巨人｜進擊的巨人 合作',
    'バレンタインナイト': '情人節之夜',
    'ハーベストフェスティバル｜転スラコラボ': '豐收祭｜關於我轉生變成史萊姆這檔事 合作',
    '盟友(我がズッ友よ)｜転スラコラボ': '盟友（我的摯友）｜關於我轉生變成史萊姆這檔事 合作',
    'ロイヤル｜ペルソナ5コラボ': '皇家｜女神異聞錄5 合作',
    '吉祥寺｜ペルソナ5コラボ': '吉祥寺｜女神異聞錄5 合作',
    '灼熱サンシャイン': '灼熱陽光',
    'クリフォトの決戦｜デビルメイクライコラボ': '克利佛特的決戰｜惡魔獵人 合作',
    'DevilMayCry5｜デビルメイクライ5コラボ': 'Devil May Cry 5｜惡魔獵人5 合作',
    'NEOミクトラン｜テイルズオブシリーズコラボ': 'NEO 米克特蘭｜傳說系列 合作',
    'エルドラントの決戦｜テイルズオブシリーズコラボ': '艾爾德蘭特的決戰｜傳說系列 合作',
    '凛々の明星｜テイルズオブシリーズコラボ': '凜然的明星｜傳說系列 合作',
    '乙女たちのXmasキャロル': '少女們的聖誕頌歌',
    'Let`s Hit The Climax!｜ベヨネッタコラボ': 'Let’s Hit The Climax!｜魔兵驚天錄 合作',
    'One Of A Kind｜ベヨネッタコラボ': 'One Of A Kind｜魔兵驚天錄 合作',
    '人体錬成｜鋼の錬金術師コラボ': '人體鍊成｜鋼之鍊金術師 合作',
    'お父様とホムンクルスたち｜鋼の錬金術師コラボ': '父親大人與人造人們｜鋼之鍊金術師 合作',
    '黒の騎士団｜コードギアスコラボ': '黑色騎士團｜Code Geass 合作',
    '優しい世界｜コードギアスコラボ': '溫柔的世界｜Code Geass 合作',
    '炎天下ウェイブウォーズ': '炎天下的浪潮戰爭',
    'エインフェリア｜ヴァルキリープロファイル −レナス−コラボ': '恩菲利亞｜女神戰記 −蕾娜絲− 合作',
    '主神オーディン｜ヴァルキリープロファイル −レナス−コラボ': '主神奧丁｜女神戰記 −蕾娜絲− 合作',
    'ラクール武具大会｜スターオーシャン セカンドストーリーRコラボ': '拉庫爾武具大會｜星海遊俠 第二故事R 合作',
    'ヴェルドラ日記｜転スラコラボ': '維爾德拉日記｜關於我轉生變成史萊姆這檔事 合作',
    '霊子崩壊｜転スラコラボ': '靈子崩壞｜關於我轉生變成史萊姆這檔事 合作',
    '聖なる夜の大滑走': '聖夜的大滑走',
    '新たな時代へ': '邁向新時代',
    'それぞれの決意': '各自的決心',
    'バレンタイン・ビート': '情人節節奏',
    '終尾の巨人｜進撃の巨人コラボ': '終尾的巨人｜進擊的巨人 合作',
    '自由の翼｜進撃の巨人コラボ': '自由之翼｜進擊的巨人 合作',
    'VS.エッグマン｜ソニックコラボ': 'VS. 蛋頭博士｜索尼克 合作',
    '秘境の街': '神隱之境',
    'シーサイド・ドライブ': '海岸線兜風',
    '共闘！｜VP1×SO2Rコラボ': '共鬥！｜VP1×SO2R 合作',
    'ダークハロウィンナイト': '暗黑萬聖夜',
    'プレアデス｜オーバーロードコラボ': '昴宿星團｜OVERLORD 合作',
    '鴉たちのクリスマス': '烏鴉們的聖誕節',
    '羅針盤｜テイルズオブシリーズコラボ': '羅盤｜傳說系列 合作',
    '領戦王争｜テイルズオブシリーズコラボ': '領戰王爭｜傳說系列 合作',
    'ゼーブル・ファー｜聖剣伝説コラボ': '傑布魯・法｜聖劍傳說 合作',
    'Cの世界｜コードギアスコラボ': 'C 的世界｜Code Geass 合作',
    'ライザのアトリエ': '萊莎的鍊金工房',
    'キャンプでの一夜': '露營一宿',
    '異界の晩餐': '異界的晚宴',
    '百の夜と千の空': '百夜與千空',
    '美シキ歌姫｜NieR:Automataコラボ': '美麗的歌姬｜NieR:Automata 合作',
    'エミールショップ｜NieR:Automataコラボ': '艾米爾商店｜NieR:Automata 合作',
    'TRIALS of MANA｜聖剣伝説コラボ3': 'TRIALS of MANA｜聖劍傳說3 合作',
    'フラミー＆ブースカブー｜聖剣伝説コラボ3': '芙拉米＆布斯卡布｜聖劍傳說3 合作',
    'グランゼリアスイートロック': '格蘭澤利亞甜蜜搖滾',
    'ある夏の日の追憶': '某個夏日的追憶',
    '崩壊紋章｜スターオーシャン セカンドストーリーRコラボ': '崩壞紋章｜星海遊俠 第二故事R 合作',
    'トリックナイト狂想曲': '詭計之夜狂想曲',
    'バンカー｜NieR:Automataコラボ': '碉堡｜NieR:Automata 合作',
    'WORLDTOUR': '世界巡迴',
    'グリーンヒルゾーン｜ソニックコラボ': '綠丘地帶｜索尼克 合作',
    '幻英の塔': '幻英之塔',
    '機械生命体｜NieR:Automataコラボ': '機械生命體｜NieR:Automata 合作',
    'ハロウィンナイトドライブ': '萬聖夜兜風',
    'Believe In Myself｜ソニックコラボ': 'Believe In Myself｜索尼克 合作',
    'ホワイトクリスマス': '白色聖誕',
    'ジャック・オー・ランタン': '傑克南瓜燈',
    '海賊船レグニス号': '海盜船雷格尼斯人號',
    '栄光のカルディナ': '榮耀的卡爾迪納',
    '古の精霊国『ママ・ネル』': '古代精靈國《媽媽・奈爾》',
    'エルマリア・ファーム': '艾爾瑪利亞農場',
    'オルダーナ帝国': '奧爾達納帝國',
    '光と炎の血族': '光與炎之血族',
    '空艇ロンヴァリオン': '空艇隆瓦里昂',
    '超砂獣の霊帝牙': '超砂獸的靈帝牙',
    '秘奥録『灼鳳破』': '秘奧錄《灼鳳破》',
    '異国メグロナ': '異國梅格羅納',
    'グラナ海の脅威': '格拉納海的威脅',
    '蒼氷の守護騎士': '蒼冰的守護騎士',
    'ゴルド戦争': '戈爾德戰爭',
    '科学の灯': '科學之燈',
    '銀灰色の剣聖譚': '銀灰色的劍聖譚',
    '叛逆の竜騎兵団': '叛逆的龍騎兵團',
    'レーディアの星禍': '雷迪亞的星禍',
    '機竜ベルディオス': '機龍貝爾迪歐斯',
    '四破神将': '四破神將',
    '精神世界-破神-': '精神世界－破神－',
    '海獣メガロドン': '海獸巨齒鯊',
    '聖都アダン': '聖都阿丹',
    'サイカのギルド': '賽卡的公會',
    '魔導神兵『ガノン』': '魔導神兵《加農》',
    '雷神天翔': '雷神天翔',
    '砂雲艦セイントローズ': '砂雲艦聖玫瑰',
    '新生デュランダル': '新生杜蘭達爾',
    '白のモノリス': '白之獨石',
    '覇竜ガラノヴァ': '霸龍加拉諾瓦',
    'ファントムクロウ': '幻影之鴉',
    'パントルベイン': '潘托爾貝因',
    '邪神サマエル': '邪神薩麥爾',
    '皇竜バハムート': '皇龍巴哈姆特',
    '炎影と氷皇': '炎影與冰皇',
    '星間船エクスペリオン': '星際船艾克斯佩里昂',
    '雷嵐の荒神': '雷嵐的荒神',
    '竜人村': '龍人村',
    '星詠みの丘': '星詠之丘',
    '神魔大戦': '神魔大戰',
    'ヘリウス神騎士団': '赫利烏斯神騎士團',
    '遥界の古代図書館': '遙界的古代圖書館',
    '地を這う神兵': '匍匐於地的神兵',
    '英雄王の覚醒': '英雄王的覺醒',
    '樹海に残されしもの': '遺留於樹海之物',
    '天聖女の凱旋': '天聖女的凱旋',
    'マジャ大神殿': '瑪賈大神殿',
    '神獣ログ・メキア': '神獸羅格・梅基亞',
    '導きの星鐘楼': '指引之星鐘樓',
    '硫酸の泉': '硫酸之泉',
    '解き放たれし獣王': '被解放的獸王',
    '災禍を穿つ者': '貫穿災禍之人',
    '古代遺跡セント・マリウス': '古代遺跡聖・馬里烏斯',
    'ゲームマスター': '遊戲大師',
    '暴食帝アバドン': '暴食帝阿巴頓',
    'オルダーナ国立魔導学院': '奧爾達納國立魔導學院',
    'セレスティアル': '天界',
    '天誘のグローリーロード': '天誘的榮耀之路',
    '腐祖竜ヘルディール': '腐祖龍赫爾迪爾',
    '魔導都市セントパーム': '魔導都市聖棕櫚',
    '深海の廃都ノノ・パクラ': '深海的廢都諾諾・帕庫拉',
    '屍山に立つ狂剣': '立於屍山的狂劍',
    '星屑のLIVE': '星塵的 LIVE',
    '暴風竜ヴェルドラ': '暴風龍維爾德拉',
    'ガリアーノ大瀑布': '加里亞諾大瀑布',
    '冥麗姫『桜月』': '冥麗姬《櫻月》',
    'キリングドール': '殺戮人偶',
    'エレメンタルアーク': '元素方舟',
    'ラストクラウディア': '最後的克勞迪亞',
    '死炎竜アグニウス': '死炎龍阿格尼烏斯',
    '天弓スターロード': '天弓星之路',
    '大天使の微笑': '大天使的微笑',
    '冥皇門デスノーグ': '冥皇門死亡諾古',
    '聖剣伝説2【聖剣伝説コラボ】': '聖劍傳說2【聖劍傳說 合作】',
    '聖剣伝説FF外伝【聖剣伝説コラボ】': '聖劍傳說 FF 外傳【聖劍傳說 合作】',
    '古代兵器ローガーン': '古代兵器羅加恩',
    'ババラードの毒竜': '巴巴拉德的毒龍',
    '死霊の大軍勢': '死靈的大軍勢',
    '砂漠の音楽隊': '沙漠的音樂隊',
    'オルダーナ帝国騎士団': '奧爾達納帝國騎士團',
    '神環アツィルト': '神環阿齊爾特',
    '三賢者': '三賢者',
    'ヴェル＝ジ＝オーグ': '維爾＝吉＝奧古',
    '聖夜の願い事': '聖夜的願望',
    '竜宝レイニクル': '龍寶雷尼克爾',
    'ゴーレム・コア': '魔像核心',
    '終末の命誓': '終末的命誓',
    '幻異門ユドレール': '幻異門尤德雷爾',
    'ブレイズガーデン': '烈焰花園',
    '爆炎の支配者': '爆炎的支配者',
    '神獣を狩る者': '獵殺神獸之人',
    '禁書の眠る祭壇': '禁書沉眠的祭壇',
    '秘宝マルキュロディン': '秘寶瑪爾丘羅丁',
    '魔獣ハンター': '魔獸獵人',
    'オルダーナ闘技場': '奧爾達納競技場',
    '緋炎の英傑': '緋炎的英傑',
    '魔鏡ポムラム': '魔鏡波姆拉姆',
    '宝剣エリュード': '寶劍艾呂德',
    '邪教神殿': '邪教神殿',
    '永久時計デ＝ロウ': '永久時鐘德＝羅',
    '白騎士の休息': '白騎士的休息',
    'STONE WORLD': 'STONE WORLD',
    '洞闇の酒坏': '洞闇的酒杯',
    '天空城の雷神': '天空城的雷神',
    'グラン・バーガン': '格蘭・巴根',
    '聖旗ノルレアン': '聖旗諾爾雷昂',
    '乙女の祈り': '少女的祈禱',
    '剣聖墓メノン': '劍聖墓梅農',
    'ゼルエンの亡霊': '澤爾恩的亡靈',
    '鏡鎧ミゼル': '鏡鎧米澤爾',
    'ポックルの隠れ里': '波克爾的隱村',
    '聖剣伝説3【聖剣伝説コラボ】': '聖劍傳說3【聖劍傳說 合作】',
    'エミールヘッド｜NieR:Automataコラボ': '艾米爾頭套｜NieR:Automata 合作',
    'ブラッディムーン': '血月',
    '隠者の禁室': '隱者的禁室',
    'ゴルドの奇跡': '戈爾德的奇蹟',
    '海竜神殿グラナ・ダリア': '海龍神殿格拉納・達莉亞',
    'ソーサラーエデン': '巫師伊甸',
    'ラドムーン賢封蹟': '拉德月賢封跡',
    '雷宝石の光輝': '雷寶石的光輝',
    'ガイエスト修剣山': '蓋艾斯特修劍山',
    '海岸線の破剣': '海岸線的破劍',
    '月下斬明': '月下斬明',
    '人工エーテル': '人工乙太',
    'アルダンの戦士': '阿爾丹的戰士',
    '白銀雪虹': '白銀雪虹',
    'フェアリーズフォレスト': '妖精森林',
    '絶断門ベガンダ': '絕斷門貝岡達',
    'ファルニアの花': '法爾尼亞之花',
    '蜃気楼の砂塔': '海市蜃樓的砂塔',
    'リバラザードの生誕': '利巴拉札德的誕生',
    '焔鳥レミの卵': '焰鳥雷米之卵',
    '聖火シュミライア': '聖火修米萊亞',
    'ポックルイーター': '波克爾吞食者',
    '交易港グラナダ': '交易港格拉納達',
    '蒼光騎士団': '蒼光騎士團',
    'ジャイアント・ツリー': '巨人之樹',
    '魔女が棲む家': '魔女棲息之屋',
    '魔獣たちの秘湯': '魔獸們的秘湯',
    'クリスタルキャッスル': '水晶城堡',
    '白の研究所': '白之研究所',
    '巨雷雲ゼラニア': '巨大雷雲澤拉尼亞',
    '異界次元の狭間': '異界次元的夾縫',
    // 基礎屬性
    'HP': 'HP', 'MP': 'MP',
    'STR': '力量', 'DEF': '防禦', 'INT': '智力', 'MND': '精神',
    'クリティカル': '爆擊', 'ダメージ': '傷害',
    '回復': '恢復', '確率': '機率', '物理': '物理', '魔法': '魔法',
    '超必殺技': '超必殺技', '特技': '特技', '技能': '技能','ストック':'充能槽',

    // 武器類型
    '両手剣': '兩手劍', '両手槍': '兩手槍', '両手斧': '兩手斧', '両手杖': '兩手杖', '両手槌': '兩手槌',
    '剣': '劍', '槍': '槍', '斧': '斧', '弓': '弓', '杖': '杖', '槌': '槌', '爪': '爪', '鞭': '鞭',
    '機械': '機械', '服': '服', '鎧': '鎧', '兜': '頭盔', '帽子': '帽子', 'アクセサリー': '飾品','アーマー':'盔甲',

    // 屬性
    '炎属性': '炎屬性', '氷属性': '冰屬性', '雷属性': '雷屬性', '樹属性': '樹屬性',
    '光属性': '光屬性', '闇属性': '暗屬性', '無属性': '無屬性',
    '炎': '炎', '氷': '冰', '雷': '雷', '樹': '樹', '光': '光', '闇': '暗',

    // 狀態異常
    '毒': '毒', '麻痺': '麻痺', '暗闇': '失明', '沈黙': '沉默', '呪い': '詛咒', '気絶': '暈眩',
    '病気': '疾病', '凍結': '凍結',

    // 常見後綴與動詞
    'アップ': '提升', 'ダウン': '降低', '無効': '無效', '半減': '減半', '吸収': '吸收',
    'ブースト': '增幅', 'ハイ': '高階', 'メガ': '超階', 'ギガ': '億萬', '極': '極', '真': '真',
    'ドライブ': '驅動', 'アタックレイズ': '攻擊提升', 'マジックレイズ': '魔力提升',
    'クリティカルレイズ': '爆擊提升', 'プラウドフォース': '榮耀之力',
    'スレイヤー': '斬滅者', 'キラー': '剋星', 'ブレイカー': '破壞者','バスター':'爆裂者',
    'サークル': '環', 'ウォール': '牆', 'フィールド': '領域','モータルリッパー':'致命裂解者',
    'シールド': '護盾', 'バリア': '屏障','エンプティ':'枯竭',
    'リサーチ': '研究', 'マスタリー': '精通', 'デヴォーション': '奉獻',
    'チャージ': '充能', 'ヘイスト': '加速', 'リキャスト': '冷卻',
    'カウンター': '反擊', 'ガード': '防禦', 'ドレイン': '吸取',
    'エスケープ': '逃脫', 'サプライズ': '奇襲','フォート':'堡壘',
    'オート': '自動', 'ファスト': '快速','スカイ':'天空','ホーリーレジスト':'聖抗',
    'ブレイブ': '鼓舞', 'オーラ': '增魔', 'プロテクト': '保護', 'マインド': '精神',

    // 種族特效
    'ソルジャー': '戰士', 'ナイト': '騎士', 'ソーサラー': '法師', 'スナイパー': '射手','ヒューマン':'人類',
    'ゴッド': '神', 'スピリット': '精靈', 'ビースト': '獸族', 'クリーチャー': '生物','ジャイアント':'巨型','キリング':'殺戮',
    'ドラゴン': '龍', 'プラント': '植物', 'インセクト': '昆蟲', 'バード': '鳥','天霊':'天靈',
    'フィッシュ': '魚', 'アンデッド': '不死', 'ストーン': '岩石', 'マシーン': '機械',

    // 特殊名詞
    '弱点突破': '弱點突破', '限界突破': '界限突破',
    '急所狙い': '瞄準要害', '不意打ち': '偷襲', '背後攻撃': '背後攻擊',
    '英雄の証': '英雄之證', '大天使の加護': '大天使的加護',
    'パープルオーブ': '紫魂石', 'ブルーオーブ': '藍魂石', 'レッドオーブ': '紅魂石',
    'アークエーテル': '乙太', 'エーテル': '乙太'
};

// 排序翻譯鍵值，確保長詞優先匹配 (例如 '両手剣' 優先於 '剣')
const SORTED_KEYS = Object.keys(SKILL_TRANSLATIONS).sort((a, b) => b.length - a.length);

function translateText(text) {
    if (!text) return '';
    let translated = text;

    // 使用正則表達式進行全域替換
    for (const key of SORTED_KEYS) {
        // 簡單的字串替換，不使用單詞邊界 (\b) 因為日文通常沒有空格
        translated = translated.split(key).join(SKILL_TRANSLATIONS[key]);
    }
    return translated;
}

// 輔助函式：產生雙語 HTML
function createBilingualHtml(jpText, className = '') {
    if (!jpText) return '';
    const zhText = translateText(jpText);

    // 如果翻譯後跟原文一樣（沒翻譯到），或原文很短（可能是數字），就只顯示原文
    if (zhText === jpText || jpText.length < 2) {
        return `<span class="${className}">${jpText}</span>`;
    }

    return `
        <div class="flex flex-col">
            <span class="${className} font-medium">${zhText}</span>
            <span class="text-xs text-gray-500 opacity-80">${jpText}</span>
        </div>
    `;
}

// State
let allArks = [];
let currentFilter = 'all';
let searchQuery = '';

// DOM Elements
const arkGrid = document.getElementById('arkGrid');
const searchInput = document.getElementById('searchInput');
const filterBtns = document.querySelectorAll('.filter-btn');
const totalCount = document.getElementById('totalCount');
const modal = document.getElementById('arkModal');
const modalPanel = document.getElementById('modalPanel');
const closeModalBtn = document.getElementById('closeModal');
const modalBackdrop = document.getElementById('modalBackdrop');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    fetchArks();
    lucide.createIcons();

    // Event Listeners
    searchInput.addEventListener('input', (e) => {
        searchQuery = e.target.value.toLowerCase();
        renderArks();
    });

    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Update UI
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update State
            currentFilter = btn.dataset.filter;
            renderArks();
        });
    });

    closeModalBtn.addEventListener('click', closeModal);
    modalBackdrop.addEventListener('click', closeModal);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });
});

async function fetchArks() {
    try {
        const response = await fetch('arks-data.json');
        const data = await response.json();

        // 定義稀有度排序權重
        const rarityOrder = { 'UR': 0, 'LR': 1, 'SSR': 2, 'SR': 3, 'R': 4 };

        allArks = data.arks.sort((a, b) => {
            const rarityA = rarityOrder[a.rarity] ?? 99;
            const rarityB = rarityOrder[b.rarity] ?? 99;
            if (rarityA !== rarityB) return rarityA - rarityB;
            return b.id - a.id;
        });

        totalCount.textContent = `Total Arks: ${allArks.length}`;
        renderArks();
    } catch (error) {
        console.error('Error fetching arks:', error);
        arkGrid.innerHTML = `
            <div class="col-span-full text-center text-red-400 py-10">
                <p>無法讀取資料 (arks-data.json)</p>
                <p class="text-sm text-gray-500 mt-2">請確認已執行 fetch-all-arks.js</p>
            </div>
        `;
    }
}

function getRarityColorClass(rarity) {
    switch(rarity) {
        case 'UR': return 'text-ur border-ur';
        case 'LR': return 'text-lr border-lr';
        case 'SSR': return 'text-ssr border-ssr';
        case 'SR': return 'text-sr border-sr';
        case 'R': return 'text-r border-r';
        default: return 'text-gray-400 border-gray-600';
    }
}

function renderArks() {
    arkGrid.innerHTML = '';

    const filtered = allArks.filter(ark => {
        const matchesFilter = currentFilter === 'all' || ark.rarity === currentFilter;
        const arkName = ark.name.toLowerCase();

        // 搜尋原文與翻譯
        let searchableText = [arkName, translateText(ark.name).toLowerCase()];

        if (ark.learnableSkills) {
            ark.learnableSkills.forEach(s => {
                searchableText.push(s.name.toLowerCase());
                searchableText.push(translateText(s.name).toLowerCase());
                if (s.effect) {
                    searchableText.push(s.effect.toLowerCase());
                    searchableText.push(translateText(s.effect).toLowerCase());
                }
            });
        }

        if (ark.etherReward) {
            searchableText.push(ark.etherReward.toLowerCase());
            searchableText.push(translateText(ark.etherReward).toLowerCase());
        }

        const matchesSearch = searchableText.some(text => text.includes(searchQuery));
        return matchesFilter && matchesSearch;
    });

    if (filtered.length === 0) {
        arkGrid.innerHTML = `
            <div class="col-span-full text-center text-gray-500 py-20">
                <i data-lucide="search-x" class="w-10 h-10 mx-auto mb-4 opacity-50"></i>
                <p>找不到符合條件的聖物</p>
            </div>
        `;
        lucide.createIcons();
        return;
    }

    filtered.forEach(ark => {
        const rarityClass = getRarityColorClass(ark.rarity);
        const card = document.createElement('div');
        card.className = `ark-card relative group bg-white/5 border border-white/10 rounded-xl overflow-hidden cursor-pointer backdrop-blur-sm ${rarityClass.split(' ')[1]}`;

        // 翻譯名稱
        const zhName = translateText(ark.name);

        card.innerHTML = `
            <div class="aspect-[16/9] overflow-hidden bg-void relative">
                <img src="${ark.image}" alt="${ark.name}" class="ark-image w-full h-full object-cover transition-transform duration-500">
                <div class="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/60 backdrop-blur-sm text-xs font-bold ${rarityClass.split(' ')[0]} border border-white/10">
                    ${ark.rarity || '?'}
                </div>
                <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-60"></div>
            </div>

            <div class="p-4 relative">
                <div class="mb-1">
                    <h3 class="font-cinzel font-bold text-gray-100 text-lg leading-tight group-hover:text-crimson transition-colors">${zhName}</h3>
                    <p class="text-xs text-gray-500 mt-1 truncate">${ark.name}</p>
                </div>

                <div class="mt-3 flex items-center justify-between text-xs text-gray-500">
                    <div class="flex items-center gap-1">
                        <i data-lucide="book-open" class="w-3 h-3"></i>
                        <span>${(ark.learnableSkills || []).length} Skills</span>
                    </div>
                    <div class="flex items-center gap-1">
                        <i data-lucide="gift" class="w-3 h-3"></i>
                        <span>${ark.etherReward ? 'Yes' : 'No'}</span>
                    </div>
                </div>
            </div>
        `;

        card.addEventListener('click', () => openModal(ark));
        arkGrid.appendChild(card);
    });

    lucide.createIcons();
}

function openModal(ark) {
    // Title
    const modalTitle = document.getElementById('modalTitle');
    modalTitle.innerHTML = `
        <div class="flex flex-col">
            <span class="text-2xl">${translateText(ark.name)}</span>
            <span class="text-sm text-gray-400 font-normal mt-1">${ark.name}</span>
        </div>
    `;

    // Rarity Badge
    const rarityClass = getRarityColorClass(ark.rarity);
    const badge = document.getElementById('modalRarity');
    badge.textContent = ark.rarity || '?';

    let badgeBg = 'bg-black/40';
    if (ark.rarity === 'UR') badgeBg = 'bg-ur/20';
    else if (ark.rarity === 'LR') badgeBg = 'bg-lr/20';
    else if (ark.rarity === 'SSR') badgeBg = 'bg-ssr/20';
    badge.className = `px-3 py-1 rounded border backdrop-blur-md shadow-lg font-cinzel font-bold tracking-widest text-lg ${rarityClass} ${badgeBg}`;

    // Images
    document.getElementById('modalImage').src = ark.image;
    document.getElementById('modalBg').style.backgroundImage = `url('${ark.image}')`;
    document.getElementById('modalLink').href = ark.url;

    // Traits (特性)
    const traitEl = document.getElementById('modalTrait');
    let traitText = '';

    if (ark.arkEffect && ark.arkEffect.length > 0) {
        traitText = ark.arkEffect[ark.arkEffect.length - 1].effect;
    } else if (ark.arkTraitSummary) {
        traitText = ark.arkTraitSummary;
    }

    if (traitText) {
        traitEl.innerHTML = createBilingualHtml(traitText, 'text-gray-200');
    } else {
        traitEl.textContent = '無特性資料';
        traitEl.classList.add('text-gray-600', 'italic');
    }

    // Ark Skill (聖物主動技能)
    const arkSkillEl = document.getElementById('modalArkSkill');
    let arkSkillText = '';
    if (ark.arkSkill && ark.arkSkill.length > 0) {
        arkSkillText = ark.arkSkill[ark.arkSkill.length - 1].skill;
    }

    const arkSkillContainer = document.getElementById('arkSkillContainer');
    if (arkSkillText) {
        arkSkillEl.innerHTML = createBilingualHtml(arkSkillText, 'text-gray-200');
        arkSkillContainer.classList.remove('hidden');
    } else {
        arkSkillContainer.classList.add('hidden');
    }

    // Ether Reward (乙太獎勵)
    const etherEl = document.getElementById('modalEther');
    const etherText = ark.etherReward || '無乙太獎勵資料';
    etherEl.innerHTML = createBilingualHtml(etherText, 'text-gray-200');

    // Skills
    const skillsContainer = document.getElementById('modalSkills');
    skillsContainer.innerHTML = '';

    if (ark.learnableSkills && ark.learnableSkills.length > 0) {
        ark.learnableSkills.forEach(skill => {
            const zhName = translateText(skill.name);
            const row = document.createElement('div');
            row.className = 'flex flex-col sm:flex-row sm:items-start justify-between p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors border border-white/5 gap-3';

            // 處理技能效果的翻譯
            const effectHtml = createBilingualHtml(skill.effect, 'text-gray-300');

            row.innerHTML = `
                <div class="flex-1 w-full">
                    <div class="flex items-center gap-2 mb-2 flex-wrap">
                        <span class="font-bold text-gray-200 text-base">${zhName}</span>
                        <span class="text-xs text-gray-500 bg-black/30 px-1.5 py-0.5 rounded border border-white/5">${skill.name}</span>
                        ${skill.type ? `<span class="text-[10px] text-gray-400 bg-white/5 px-1 rounded">${skill.type}</span>` : ''}
                    </div>
                    <div class="text-sm leading-relaxed space-y-1">
                        ${effectHtml}
                    </div>
                </div>
                <div class="flex flex-col items-end gap-1 shrink-0">
                    <span class="text-xs font-mono text-blue-300 bg-blue-900/30 px-2 py-1 rounded border border-blue-500/20 whitespace-nowrap">SC: ${skill.sc}</span>
                    ${skill.ap ? `<span class="text-[10px] text-gray-500">${skill.ap}</span>` : ''}
                </div>
            `;
            skillsContainer.appendChild(row);
        });
    } else {
        skillsContainer.innerHTML = '<p class="text-sm text-gray-500 italic p-2">無可習得技能</p>';
    }

    // Show Modal
    modal.classList.remove('hidden');
    setTimeout(() => {
        modal.classList.remove('opacity-0');
        modalPanel.classList.remove('scale-95', 'opacity-0');
    }, 10);

    document.body.style.overflow = 'hidden';
}

function closeModal() {
    modal.classList.add('opacity-0');
    modalPanel.classList.add('scale-95', 'opacity-0');

    setTimeout(() => {
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }, 300);
}
