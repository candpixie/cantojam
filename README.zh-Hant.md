# cantojam 協音

<p align="center">
  <b>繁體中文</b> · <a href="README.md">English</a>
</p>

**粵語歌詞的協音工具，一切以語料實測為準，而非憑經驗推斷。**

**網頁版：https://candpixie.github.io/cantojam/** — 輸入歌詞、拖曳音符、即時試聽、
尋找可用的字詞。無伺服器、無上載、可離線使用。

粵語有六個聲調，旋律若與聲調背道而馳，字就會被聽成另一個字。填詞人向來明白這一點，
坊間口訣（0243、02493、394052）正是把它化成一把音高階梯，靠耳朵對應。

cantojam 以 37,877 個實際唱出的音節驗證這把階梯，發現它大致準確，但有兩處明顯偏差。
在此之上，它做到兩件其他查詢工具做不到的事：

- **`check`**：已有旋律與歌詞時，旋律有沒有與聲調衝突？
- **`contour`**：已有歌詞但未有旋律時，聲調其實已決定了大部分形狀，此功能將其還原。

```
$ cantojam contour lyrics.txt --key "F major" --section verse --spread 2

今日天氣真係好
  G4 今 · 天 · 真 · ·
  F4 · · · · · · 好
  D4 · · · 氣 · · ·
  C4 · 日 · · · 係 ·
     今 日 天 氣 真 係 好
     1  6  1  3  1  6  2
  notes: G4 C4 G4 D4 G4 C4 F4
```

## 安裝

```bash
pip install -e .
```

不依賴任何套件，需要 Python 3.9 或以上。

## 語料實測結果

執行 `cantojam model` 可查看全部數字，以下為重點。

**37,772 對相鄰音節的「聲調走向 × 旋律走向」**

| 聲調 | 旋律下行 | 旋律持平 | 旋律上行 |
| --- | --- | --- | --- |
| 下行 | **84.9%** | 9.4% | 5.7% |
| 持平 | 34.7% | 42.8% | 22.5% |
| 上行 | 3.3% | 7.1% | **89.7%** |

直接相衝者僅佔 2.8%。可見在商業粵語流行曲之中，協音並非一種偏好，而是接近硬性的規則。

**各聲調的實際音高位置**（相對該首歌的中位音高，單位為半音）：

```
第一聲  +2.22   陰平
第二聲  +1.96   陰上
第三聲  -0.35   陰去
第五聲  -0.46   陽上     ← 與第三聲同一水平，而非與第六聲同級
第六聲  -1.34   陽去
第四聲  -4.31   陽平     ← 是一道懸崖，而非一級階梯
```

由此得出對傳統四級階梯的兩項修正：

1. **第五聲與第六聲不可互換。** 0243 將兩者歸為同一級，但在語料之中，
   六→五有 96.7% 向上行，五→六有 92.8% 向下行。若視為同一高度處理，
   等於在絕大多數情況下都會弄錯方向。第五聲應與第三聲並列。
2. **第四聲並非低於第六聲一級，而是三級。** 由第四聲行至第一聲，音程中位數為
   **+8 個半音**；其餘所有聲調組合的差距，皆在一至兩個全音之內。

在 36 個聲調組合之中，有 23 個呈一面倒（單一方向佔比 ≥80%），cantojam 將其視為硬性規則；
其餘的確實自由，包括所有同聲調的組合。

**段落之間有可量度的音高差異。** 相對全首中位數：主歌 −3、前副歌 −1、副歌 +1、
橋段 +2。換言之，由主歌進入副歌約提升四個半音。

## 網頁版

以下所有功能同樣可在瀏覽器直接使用：
[candpixie.github.io/cantojam](https://candpixie.github.io/cantojam/)

- 一邊輸入歌詞，一邊看著聲調所要求的旋律輪廓浮現。
- **拖曳任何一個音符**，旋律一旦與字音衝突，連線即時轉為紅色，游標停留更會顯示語料證據。
- 可即時試聽，或匯出 MIDI 至自己的 DAW。
- **字詞搜尋**：點選一個音符，它會列出該段旋律真正容納得下的字詞，並可加上押韻條件。
  這個交叉點是其他工具做不到的。

整體為靜態網頁。模型僅 109 KB JSON 加約 250 行 JavaScript，因此沒有後端、
不會上載任何內容，在飛機上亦可使用。`web/cantojam.js` 為 Python 版本的人手移植，
而 `tests/test_parity.py` 會以同一批輸入同時執行兩者，一旦出現分歧即測試失敗。

## 用法

### 檢查現有旋律

```bash
$ cantojam check "係我" "G4 C4"
 X 我  ngo5     C4    -7

  X 係我 (tone 6->5) should rise; this melody falls.
    Corpus median +1 semitones over 1559 examples.

1 violation(s) in 2 syllables
```

發現問題時回傳非零結束碼，因此可直接掛在 pre-commit hook，或對整個歌詞資料夾執行 CI。

嚴重程度分為兩級：

- **violation**（`X`）：語料有 ≥80% 走相反方向，聽眾會聽成另一個字。
- **unusual**（`?`）：並無硬性規則，但此走法極為罕見。例如由第一聲再上第一聲，
  在語料中僅佔 5.2%，因為第一聲之上已無空間。唱得出來，只是少見。

### 由歌詞推導旋律

```bash
cantojam contour lyrics.txt --key "F major" --center F4 --section chorus --spread 2
```

每個音節先置於其聲調應有的高度，再以 beam search 在各條音階路徑之中，
選出一條既符合硬性聲調規則，又能收於主音或屬音、走出弧線、採用語料常用音程，
並在可行時呼應前面相同聲調組合的旋律。加上 `--json` 即可接入 DAW 腳本。

聲調規則其實留下很大空間：36 個組合之中僅 23 個規定方向，因此合法的旋律有許多條，
此搜尋是在其中挑選，而非「找到第一條可行的便算」。以 300 句語料歌詞實測，
原有的貪心修補方式收於主音或屬音的比率為 **0%**，而搜尋達到 **55%**，
違規數同樣為零。

`--spread` 可放大或收窄音域而不改變形狀。單靠聲調高度會得出很窄的旋律線，
因為聲調只需要「分辨得出」，並不需要誇張；真實旋律會因音樂上的理由走得更遠。
建議在 1.5 至 2.5 之間嘗試。

**這是骨架，並非一首旋律。** 它只固定輪廓，節奏、分句、重複等等全數留給你。
其用意是突破白紙，而非代你填滿。

### 查詢聲調

```bash
$ cantojam tones "今日天氣真係好"
  今  gam1     tone 1
  日  jat6     tone 6
  天  tin1     tone 1   polyphone: tin1/jik1
  氣  hei3     tone 3
  真  zan1     tone 1
  係  hai6     tone 6
  好  hou2     tone 2   polyphone: hou2/hou3
```

多音字預設採用語料中最常見的讀音。若某首歌需要固定讀法，可用 `--override 話=waa2`。

### 尋找可用的字詞

```bash
$ cantojam words --fits "今日天氣真係好:4" --rhymes 好 --limit 6
176 word(s) fit 今日天氣真係好 at position 4, where 真係 sits

  得到     dak1 dou2              tones 12    -ou    30x
  擁抱     jung2 pou5             tones 25    -ou    19x
  一早     jat1 zou2              tones 12    -ou    14x
  不到     bat1 dou3              tones 13    -ou    13x
  好好     hou2 hou2              tones 22    -ou    13x
  多好     do1 hou2               tones 12    -ou    12x
```

**這並非字典。** 它是語料中填詞人實際寫過的 12,782 個詞語與片語，
每一條均附有聲調型態、韻母及使用次數。就填詞而言，這比字典更有用，
因為其中每一條本身已合乎語域、本身已唱得出來。它不會收錄冷僻的文言詞彙，也不應收錄。

不加 `--fits` 時，它即是一般的押韻與聲調查詢：

```bash
cantojam words --rhymes 好 --length 2         # 與「好」押韻
cantojam words --tones "46" --min-count 5     # 聲調型態為四、六
cantojam words --contains 心 --tones "1?"     # 可使用通配符
```

加上 `--fits` 後，它會與旋律取交集：候選詞內部每一項聲調規則皆須成立，
同時要與前後兩端的音節銜接得上。旋律一旦固定，它所容納的聲調亦隨之固定，
而只有部分字詞帶有那個聲調型態。

## 涵蓋範圍與限制

使用前請留意以下各點：

- **語料僅有 105 首，年份為 2000 至 2020。** 其中六成由林夕與黃偉文填詞。
  它反映的是主流電台粵語流行曲，2020 年之後完全沒有涵蓋，
  當代獨立路線（Gareth.T、Kiri T、serrini）亦不在其中。
- **語料以書面語為主。** 常見口語字極少出現，因此需以 `data/colloquial.json`
  人手補充。口語歌詞的涵蓋率尚可，但並不完整。查不到的字會明確標示，絕不猜測。
- **多音字按頻率判定**，以字次計算約有 94% 正確。要緊的位置請使用 `--override`。
- **只處理旋律。** 沒有和聲，沒有節奏。聲調只約束輪廓，並不約束全部。
- **輪廓輸出是起點。** 它懂得收句、懂得走弧線，但對節奏、分句以至歌曲內容一無所知。
  一句合乎音律的歌詞，不等於一句好的歌詞。
- **詞表是語料詞彙，並非字典。** 12,782 條全部出自這 105 首歌。較長的條目屬原始
  n-gram，其中少數跨越了詞界，可依使用次數自行判斷。若需要真正的粵語字典
  （181,220 條），請使用 [Canto-0243](https://github.com/bill-iu/Canto-0243)，
  它做得非常出色，而 cantojam 並未取用其中任何內容。

## 重建模型

```bash
git clone https://github.com/jasonleeubc/Cantopop-corpus
python scripts/build_model.py Cantopop-corpus/Humdrum-files corpus/
python scripts/build_lexicon.py Cantopop-corpus/Humdrum-files corpus/
python scripts/sync_web_data.py          # 更新瀏覽器所用的資料
python scripts/validate.py Cantopop-corpus/Humdrum-files corpus/
```

可傳入任意數量的資料夾，程式會合併處理。放於 `corpus/` 的新記譜會與上游語料一併計算。

`validate.py` 會以建立出來的模型，反過來檢查原本的語料。真實的粵語流行曲理應通過
自身的規則，事實亦然：

```
105 songs, 37772 adjacent syllable pairs
violations: 1477 (3.91%)
unusual:     287 (0.76%)
clean:     36008 (95.33%)
```

那 3.91% 便是模型對照專業填詞人時的自身誤差率。加入更多歌曲，
尤其是 2020 年之後及口語成分較重的作品，這個數字便會改善。

## 參與貢獻

**最有用的貢獻是加入一首歌。** 上述每一個數字皆出自這 105 份記譜，
因此語料一經擴充，模型即時進步，完全不需改動任何程式碼。
缺口十分具體，詳見 [`corpus/README.md`](corpus/README.md)：2020 年之後的歌曲、
口語歌詞、獨立音樂人，以及林夕與黃偉文以外的填詞人。

```bash
cp corpus/TEMPLATE.krn corpus/X0001.krn   # 加以編輯
python scripts/check_krn.py corpus/       # 每個 PR 的 CI 均會執行
```

一首歌已是實質的貢獻。其餘待辦項目（包括判斷失誤回報、韻腳抽取等）
見 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 測試

```bash
pip install -e ".[dev]"
pytest
```

## 鳴謝

模型建基於
[Jason Lee 的粵語流行曲語料庫](https://github.com/jasonleeubc/Cantopop-corpus)
（CC BY 4.0）。亦感謝 [Canto-0243](https://github.com/bill-iu/Canto-0243) 的啟發：
它是目前最好用的離線填詞查找工具，也令「欠缺旋律維度」這個空白變得顯而易見。
本專案並未使用其中任何程式碼或資料，完整說明見 [ATTRIBUTION.md](ATTRIBUTION.md)。

## 授權

程式碼採用 MIT。兩個衍生資料檔跟隨來源語料採用 CC BY 4.0，
詳見 [DATA_LICENSE.md](DATA_LICENSE.md)。
