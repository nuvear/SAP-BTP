# Northwind Advisor 受講者ワークブック

Raj Academy · 2026年9月18日

「Governed AI on SAP BTP」セッションのハンズオン教材で、2つのパートから構成されています。パートAは、公開リポジトリを使って自分のラップトップ上で実行します。SAP BTPアカウント、APIキー、パスワードは一切不要で、所要時間は約90分です。パートBは、講師のデモと同じように、自分の無料SAP BTPトライアルアカウント上に本物のSAPサインイン付きで同じアドバイザーを構築します。所要時間は約4時間です。持ち物: 管理者権限のあるラップトップ、Node.js 20以上、Python 3.11以上、git。パートBではさらに、SAPの確認コードを受け取るための携帯電話と、任意でClaudeアカウントが必要です。

# パートA: ラップトップ演習

## 演習で構築するもの

デモで見た3つの構成要素を、自分のマシン上でそのまま実行します。行ルールを持つNorthwindデータサービス、ドキュメントフィルターを持つポリシーストア、そして3つの読み取り専用ツールを提供するMCPサーバーです。SAPサインインの代わりに組み込みのテストユーザーが2人用意されており、Claudeの代わりにMCP Inspectorを使います。MCP Inspectorは、ツールを手動で呼び出して、返ってくる結果をそのまま確認できる小さなWebページです。これこそがこのワークブックの狙いです。モデルが文章に変換する前の、生の回答を確認することにあります。

| テストユーザー | オフィス | ロール | 読み取れる受注 | 読み取れるドキュメント |
| --- | --- | --- | --- | --- |
| `nancy` | シアトル | SalesHQ | 全830件 | all-staff, sales, sales-seattle |
| `steven` | ロンドン | SalesRegion、国はUK | 英国の営業担当者の受注224件 | all-staff, sales, sales-london |

演習の日付は2026年5月7日に固定されています。サンプルデータが2026年5月6日で終わっているためです。ルールの中で「今日」と言うときは、常にこの日付を指します。

必要なもの: Node.js 20以降、Python 3.11以降、git、そしてブラウザーです。`node --version`、`python3 --version`、`git --version` で確認してください。Windowsユーザーの方へ: PowerShellまたはWSLを使用してください。以下のコマンドはUnix系シェル向けに書かれており、PowerShellで異なる箇所には注記があります。

## セットアップ: 3つのターミナル、約20分

コードを一度だけ取得します。

```bash
git clone https://github.com/nuvear/SAP-BTP.git
cd SAP-BTP/apps
```

**ターミナル1、データサービス。** これは受注データと行ルールを管理するSAP CAPサービスです。ローカルではインメモリデータベースと、モックされた2人のユーザーを使用します。

```bash
cd northwind-service
npm ci
npm test
npm start
```

`npm test` は `# pass 9` と `# fail 0` で終わらなければなりません。`npm start` は `http://localhost:4004` を含む行に続けて `server ... launched` を出力します。SQLiteが実験的機能であるという警告は正常です。そのまま実行したままにしておいてください。ブラウザーで <http://localhost:4004/odata/v4/northwind/Orders?$top=3> を開くと、ユーザーを求められます。`nancy`、パスワード `nancy` と入力すると、3件の受注がJSONで表示されます。これがアシスタントの読み取るデータです。

**ターミナル2、MCPサーバー。** 3つのツールを提供し、ローカルではリポジトリにすでに含まれている86件のポリシーパッセージ（`policy-loader/chunks.jsonl`）に対するキーワード検索を使用します。

```bash
cd mcp-servers
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
DEV_MODE=1 DEV_USER=nancy LAB_TODAY=2026-05-07 python server.py advisor
```

`pytest` は 45 passed と表示しなければなりません（非推奨の警告が数件出るのは正常です。テストは別のポートでデータサービスの独自コピーを起動するため、ターミナル1と干渉しません）。最後のコマンドは `Uvicorn running on http://0.0.0.0:8000` を出力します。どのユーザーを選んだかは表示されないので、起動前に変数を確認してください。PowerShellでは、`.venv\Scripts\Activate.ps1` で有効化し、`python server.py advisor` の前に `$env:DEV_MODE="1"; $env:DEV_USER="nancy"; $env:LAB_TODAY="2026-05-07"` で変数を設定します。

`DEV_MODE=1` の意味: ラップトップにはSAPサインインがないため、サーバーは `DEV_USER` からユーザーを取得します。BTPではこのスイッチは存在せず、サーバーは有効なSAPトークンのない呼び出しをすべて拒否します。このスイッチを付けたまま絶対にデプロイしないでください。

**ターミナル3、MCP Inspector。** これがツールをのぞく窓口です。

```bash
npx @modelcontextprotocol/inspector
```

ブラウザーページが開きます。トランスポートに **Streamable HTTP** を選び、URLに `http://localhost:8000/mcp` を入力して **Connect** をクリックし、続いて **List Tools** をクリックします。`get_order_status`、`get_product_availability`、`search_policies` が表示されるはずです。Connectに失敗する場合は、ターミナル2がまだ実行中であること、URLが `/mcp` で終わっていることを確認してください。

後でStevenになるには、ターミナル2のサーバーをCtrl+Cで停止し、`DEV_USER=steven` を付けて再起動してから、Inspectorでもう一度Connectをクリックします。（再起動しない方法: Inspectorでカスタムヘッダー `X-Dev-User: steven` を追加します。ヘッダーの方が変数より優先されます。）

## 演習1: ライブの事実と行ルール（15分）

Inspectorで `get_order_status` を選択し、`order_id` = `11019` を入力して Run Tool をクリックします。

- [ ] 書き留めること: 顧客、営業担当者とそのオフィスの国、納期、`days_until_required`、運送業者、そして2つの商品明細とその在庫。`data_read_at` にも注目してください。すべての事実には、それが読み取られた時刻が付いています。
- [ ] `11070` でもう一度実行します。営業担当者はAndrew Fuller、オフィスは米国です。`days_until_required` を書き留めてください。
- [ ] 次にStevenになります（ターミナル2を `DEV_USER=steven` で再起動し、再接続します）。`11019` と `11070` について `get_order_status` を実行します。

期待される結果: Stevenとしては、11019は返ってきます（営業担当者が英国オフィスに所属しているため）が、11070は `found: false`、「No order with this number is visible to you.」と応答します。これを判断したのはMCPサーバーではありません。MCPサーバーは同じリクエストを別のユーザーとしてデータサービスに送り、データサービスの行ルールが応答したのです。ターミナル1を見てください。両方のリクエストが記録されており、2つ目のリクエストの後に `404 - Error: Not Found` が続いています。

なぜ言葉遣いが重要なのか。ツールが存在する前は、受注11019について尋ねられたモデルは、学習時に覚えたパターンから自信たっぷりに回答していたでしょう。受注11019はこの演習用データベースにしか存在しないため、その回答は捏造（ハルシネーション）だったことになります。ここで見る値はすべて、呼び出しの瞬間に行から読み取られたものであり、`data_read_at` がその時刻を示しています。グラウンディングは、捏造を検索取得に置き換えるのです。

- [ ] `get_product_availability` を `Rössle Sauerkraut` と `Chai` で試してください。一方は在庫が残っている廃番商品で、もう一方は通常の商品です。どのフィールドでそれが分かりますか。

質問（一文で答えてください）: サーバーはなぜ「does not exist（存在しない）」や「you are not allowed（許可されていない）」ではなく「not visible to you（あなたには表示されない）」と言うのでしょうか。（下に答えを書いてください。解答例は講師が持っています。）

## 演習2: 引用付きのルール（15分）

Nancyに戻ります。`search_policies` を選択し、`k` は4のままにします。

- [ ] 質問: `How much discount can I give a customer on my own authority?`（自分の権限で顧客にどれだけの値引きができますか）返ってきた各パッセージの `citation` を読んでください。どのドキュメントのどのバージョンが答えを示しており、その数値はいくつですか。
- [ ] リポジトリの `data/northwind/robustness/` を見てください。廃止済みのDiscount Authority Policy 1.0と、春のキャンペーンに関するドラフトメモを開きます。そこにはどんな上限が書かれていますか。それらは検索結果に返ってきましたか。なぜ返ってこなかったのでしょうか。（ヒント: `policy-loader/chunks.jsonl` の各パッセージには `status`、`effective_from`、`effective_to`、`audience` が付いており、ツール結果には最初の3つが表示されます。`search_policies` は、current であり、演習日時点で有効であり、かつあなたが読めるパッセージだけを検索します。）
- [ ] 質問: `customer wants a rush job, is that allowed?`（顧客が急ぎの対応を希望していますが、認められますか）パッセージには「rush job」という語句は含まれていません。それでも検索が正しいルールを見つけられた理由を説明しているのはどのパッセージですか。（用語集を探してください。）
- [ ] 質問: `Which carrier may carry seafood?`（どの運送業者がシーフードを運べますか）次に演習1と組み合わせます。受注11019には運送業者3で運ばれるシーフードの明細があります。この受注はどう扱われるべきで、誰が費用を負担し、誰が承認しますか。セクションを引用してください。

ローカルとBTPでの検索の仕組みの違いについて。ラップトップ上ではキーワード検索（BM25）で、語が一致するため用語集の項目が見つかります。BTPでは同じ質問がSAP HANAの組み込み関数で埋め込みベクトルに変換され、意味で比較されます。そのため、質問と共通する語がまったくなくても、迅速出荷（expediting）に関するパッセージが最初に返ってきます。フィルターは両方で同一です。ランキングの前に適用され、HANAでは `WHERE` 句、ローカルでは関数 `visible()` で行われます。

## 演習3: アイデンティティが決める（10分）

同じ質問を、2人の人物で。

- [ ] Nancyとして: `search_policies` に `How far are we prepared to go on the QUICK-Stop contract discount?`（QUICK-Stopの契約値引きはどこまで譲歩できますか）と入力します。引用を書き留めてください。その中に交渉上の数値はどこかにありますか。
- [ ] Stevenになって、まったく同じ質問をします。今度はLondon Sales Managerからのメモが表示されます。ドキュメントID、セクション、そしてそこに含まれる数値は何ですか。
- [ ] `data/northwind/corpus/` にあるメモのファイルを見てください。そのメモを制限している行を見つけます。次に `apps/mcp-servers/identity.py` を開き、ローカル用にNancyとStevenのドキュメントオーディエンスが定義されている箇所を見つけてください。

注目すべき点: Nancyは、何かが自分から隠されていることを知らされません。アシスタントは自分に見えるものから回答し、何が見えるかはアイデンティティに付随するオーディエンスリストによって決まります。質問の内容によって決まることは決してありません。BTPでは、このリストはSAPのロールコレクションとサインイントークン内の `country` 属性から導出されます（`apps/mcp-servers/xsuaa.py`、関数 `audiences_for`）。ローカルでは2人のテストユーザーから得られます。

宣言されているだけで、証明はされていない。ラップトップでは誰もサインインしません。`DEV_USER`（または `X-Dev-User` ヘッダー）がユーザー名を指定し、`identity.py` の `DEV_USERS` がその名前にドキュメントオーディエンスとデータサービス用のBasic認証ログインを与え、`package.json` にあるデータサービスのモックユーザーがそのログインにロールと国を与えます。誰でも `DEV_USER=steven` と入力すればStevenになれます。だからこそBTPにはこのスイッチが存在しないのです。BTPでは、ロールと国という同じ2つの事実が、MCPサーバーが検証（署名、有効期限、発行者、オーディエンス）し、データサービスが再度検証するXSUAAトークンの中に入って届きます。パートAはアイデンティティの効果を示し、パートBはその証明を示します。Lab Guide（`04_Lab_Guide`）では、各演習をこの観点からペルソナごとに説明しています。

任意: 演習の日付を変えてみましょう。`LAB_TODAY=2026-08-01` でサーバーを再起動し、Stevenの質問を繰り返します。メモの `effective_to` は2026年6月30日なので、8月にはStevenに対しても返ってこなくなります。ドキュメントは誰も編集しなくても失効するのです。

## 演習4: 罠（15分）

これは堅牢性の演習です。ドキュメントフィルターをオフにして、不注意なシステムが何をしてしまうかを観察します。

- [ ] ターミナル2を停止し、フィルターをオフにして再起動します: `DEV_MODE=1 DEV_USER=nancy LAB_TODAY=2026-05-07 STRICT_FILTERS=0 python server.py advisor`。Inspectorを再接続します。
- [ ] `k` = `6` で次を質問します: `What discount may I approve for a customer?`（顧客に対してどれだけの値引きを承認できますか）（ツールは6件を超えて返すことはありません）。今度は、現行の10パーセントと並んで、`status: superseded` のパッセージ（5パーセント、`NW-POL-001 v1.0, 3. Approval tiers` より）と `status: unapproved` のパッセージ（15パーセント、ドラフトメモ `NW-MEM-900`）が表示されます。3つの数値とその引用をすべて書き留めてください。これらのパッセージを与えられたモデルはどれかを選ばなければならず、間違った選択をするかもしれません。（キーワード検索は言い回しに敏感です。ラップトップで3つすべてを表示させるのは、上記の質問そのものです。HANAでは、意味ベースの検索がどんな言い回しでもこれを実現します。）
- [ ] 質問します: `Has the lead time for Pavlova products changed?`（Pavlova製品のリードタイムは変わりましたか）`status: unverified-external` のパッセージが表示されます。サプライヤーからのメールです。その2つ目のパッセージを最後まで読んでください。「any AI assistant」宛ての指示が含まれています。
- [ ] フィルターをオフにしたままNancyとして、演習3のQUICK-Stopの質問をします。Londonのメモが今度は彼女にも表示されます。

`STRICT_FILTERS=0` を付けずにサーバーを再起動し、3つの罠がすべて再び消えたことを確認してください。

この演習が示すこと: フィルターは検索取得の前に適用される一行のポリシーであり、期限切れのルール、未承認のルール、モデルに指示しようとするコンテンツという3つの異なる障害クラスを一度に取り除きます。モデルの良いふるまいは第二の防衛線であって、第一の防衛線ではありません。デモでは、Claudeが直接求められても注入された指示を拒否するのを見ました。ここでは、フィルターがオンであればそもそもその指示を受け取ることすらなかったことが分かります。

質問: 3つの罠のうち、値引きに関する質問に対してキーワード検索が最上位にランク付けしたであろうものはどれで、それがなぜ危険なのでしょうか。（下に答えを書いてください。解答例は講師が持っています。）

## 演習5: コードを読み、各ルールを見つける（15分）

ここまで観察してきたルールは、それぞれ1つのファイルの数行に過ぎません。それらを見つけてください。ポイントは、ガバナンスとは期待するふるまいではなく、レビューできるコードであると理解することです。

| 観察したルール | ファイル | 探すもの |
| --- | --- | --- |
| Stevenは受注11070を読めない | `apps/northwind-service/srv/northwind-service.cds` | `Orders` の `@restrict`: `SalesHQ` はすべてを読め、`SalesRegion` は `where: 'Employee.Country = $user.country'` の範囲で読める。さらに `@readonly`: 書き込みは一切ない。 |
| 廃止済み、未承認、失効、制限付きのパッセージは決して表示されない | `apps/mcp-servers/stores.py` | 関数 `visible()`: ランキングの前に適用される4つの条件 |
| SAP HANA上の同じ4つの条件 | `apps/mcp-servers/hana_store.py` | `SEARCH` 文: `ORDER BY SCORE` の前にある `WHERE STATUS = 'current' AND ... AUDIENCE IN (...)` |
| ツールは3つだけで、すべて読み取り専用 | `apps/mcp-servers/server.py` | 関数 `build()`: 3つの `@mcp.tool()` 関数だけで、それ以外は何もない。汎用クエリツールは存在しない |
| ローカルでのユーザーの決定 | `apps/mcp-servers/identity.py` | `DEV_USERS`、および `DEV_MODE` が `1` でないときにすべてを拒否する行 |
| BTPでのユーザーの決定 | `apps/mcp-servers/xsuaa.py` | `verify_token`: 署名、有効期限、発行者、オーディエンスをこの順に検証。`audiences_for`: ロールスコープと `country` 属性がドキュメントオーディエンスになる |
| BTP上でサーバーは認証なしで起動できない | `apps/mcp-servers/server.py` | 関数 `auth_config()`: XSUAAバインディングも `DEV_MODE` もないときの `SystemExit` |
| パッセージ内のテキストはデータであり、命令ではない | `apps/mcp-servers/policy_tools.py` と `server.py` | すべての検索結果に含まれる `note` フィールドと、モデルに渡される `INSTRUCTIONS` テキスト |

- [ ] 1か所を変更してテストが失敗するのを観察します: `stores.py` で、廃止済みパッセージに対して `visible()` が `True` を返すようにし、`python -m pytest -q` を実行して、どのテストが失敗し何を伝えているかを読んでください。その後、元に戻します。
- [ ] `tests/test_xsuaa.py` を読んでください。ローカルの鍵で署名した偽のSAPトークンを作成し、4つの検証ルールのそれぞれが不正なトークンを拒否する様子を示しています。別のSAPアプリケーションから盗まれたトークンを捕捉するのはどのテストですか。

## さらに進むために

**Inspectorの代わりにClaude Desktopで対話する。** Claude DesktopはローカルのMCPサーバーを直接実行できます。設定ファイル（Claude Desktop > Settings > Developer > Edit Config）を編集し、次のようなエントリーを自分のパスに置き換えて追加します。ターミナル1は実行したままにしておいてください。

```json
{
  "mcpServers": {
    "northwind-local": {
      "command": "/full/path/to/SAP-BTP/apps/mcp-servers/.venv/bin/python",
      "args": ["/full/path/to/SAP-BTP/apps/mcp-servers/server.py", "advisor", "--stdio"],
      "env": {
        "DEV_MODE": "1",
        "DEV_USER": "nancy",
        "LAB_TODAY": "2026-05-07",
        "NORTHWIND_SERVICE_URL": "http://localhost:4004/odata/v4/northwind",
        "POLICY_CHUNKS": "/full/path/to/SAP-BTP/apps/policy-loader/chunks.jsonl"
      }
    }
  }
}
```

Claude Desktopを再起動し、デモの4つの質問をしてください。`DEV_USER` を `steven` に変更して再起動し、もう一度同じ質問をします。これで、Claudeが文章を書く完全なデモがラップトップ上で動いています。

**自分のSAP BTPトライアルアカウントにデプロイする。** これがコースの後半で、約半日かかります。手順はリポジトリにあります: `apps/DEPLOY.md`（自然言語処理オプション付きのHANA Cloudインスタンス、データサービス、ロールコレクション）と `apps/DEPLOY-MCP.md`（SAPサインイン付きのMCPサーバーとClaudeコネクター）です。苦労して学んだ2つの教訓がすでに書き込まれています: `requirements.txt` で `mcp<2` に固定すること、そして `cf cups` の値は1つずつ入力することです。`apps/phase0/hana_checks.sql` は、何かをロードする前に、HANAインスタンスがテキストを埋め込みベクトルに変換できることを検証します。

**自分のドキュメントを持ち込む。** `.txt` または `.pdf` を `data/northwind/corpus/` に置き、ステータス、有効期間、オーディエンスを付けて `manifest.json` に追加し、`apps/policy-loader` で `python loader.py --data ../../data/northwind --out chunks.jsonl` を実行して、サーバーを再起動します。これであなたのドキュメントも、他のすべてと同じフィルターのもとで検索可能になります。`"status": "draft"` を付けてみて、見えないままになることを確認してください。

## 振り返り

振り返り（チームで話し合ってください）:

1. 4つのルール（行、ドキュメント、ツール、アイデンティティ）のうち、あなたの組織がコードとして表現するのに最も苦労するのはどれですか。また、それは現在どこに存在していますか。
2. アシスタントはNancyに「この情報はあなたには利用できません」と答えました。制限付きドキュメントが存在すること自体は伝えるべきでしょうか。伝えた場合、何が変わりますか。
3. フィルターはステータス、有効期間、オーディエンスを使っています。あなたの組織のポリシーでは、他にどのドキュメント属性が重要で、誰がそれを維持管理しますか。
4. Claudeを別のモデルに置き換えた場合、ここで見たふるまいのうちどれが変わり、どれがモデルに関係なくプラットフォームによって保証されますか。

# パートB: 自分のSAP BTPテナント

パートAでは、すべてが2人のテストユーザーとともにラップトップ上で動いていました。パートBでは、講師のデモとまったく同じように、本物のSAPサインイン付きの無料SAP BTPトライアルアカウント上に同じアドバイザーを構築します。6つのセクションで合計約4時間、この順番で進めます。各セクションの終わりには、画面で確認できるチェックがあります。リージョン: このハンドブックのすべてのアドレスがあなたのものと一致するよう、**Singapore (Azure)** を選んでください。他のリージョンでも動作しますが、ホスト名が異なります。

SAPの画面に入力するものは自分の手元に置いておいてください: DBADMINのパスワード、POLICY\_READERのパスワード、コネクターのクライアントシークレットです。これらをリポジトリ内のファイル、チャット、スクリーンショットに決して残さないでください。

## 1. トライアルアカウントの作成（15分）

1. <https://account.hanatrial.ondemand.com> を開き、**Get started**（SAP Universal IDをお持ちでない場合は **Register**）をクリックします。名前、メールアドレス、パスワードを入力します。SAPからメールで確認コードが届くので、入力します。
2. サインインします。トライアルの利用規約に同意します。SAPが携帯電話番号を求め、SMSでコードを送ってくるので、入力します。（Universal IDごとにトライアルは1つです。すでにお持ちの場合、このステップはそのまま既存のトライアルに進みます。）
3. リージョン **Singapore - Azure** を選んで確定します。アカウントがセットアップ中であることを示すページが表示され、1分ほどかかります。
4. **Go To Your Trial Account** をクリックします。BTPコックピットのグローバルアカウント（名前が `trial` で終わります）に入ります。サブアカウントのタイル **trial** をクリックします。
5. サブアカウントのOverviewで、Cloud Foundry Environmentのボックスを読みます: APIエンドポイント `https://api.cf.ap21.hana.ondemand.com`、`trial` で終わるorg名、さらに下に `dev` という1つのスペースがあります。org名をシートに書き留めてください。`cf target` で必要になります。
6. 左メニューで **Entitlements** をクリックします。SAP HANA Cloudを探すと、プラン `hana-free` と `tools` が表示されています。SAP AI Coreは含まれていません。このコースがClaudeを直接呼び出すのはそのためです（スライド14）。

チェック: APIエンドポイントとorg名が表示されたOverviewページ。

## 2. 環境の準備（60分、待ち時間を含む）

この順番で進めてください。最初の2つはデータベースより先に行わなければなりません。そうしないとデータベースの画面が開きません。

**2a. SAP HANA Cloud toolsのサブスクリプション。** 左メニュー **Instances and Subscriptions** > **Create**。Service: `SAP HANA Cloud` と入力して選択。Plan: `tools`（InstancesではなくSubscriptionsの下）。**Create** をクリックします。Subscriptionsのリストに Processing と表示され、続いて Subscribed になります（1分ほど）。

**2b. ロールコレクション。** 左メニュー **Security > Users**、自分のユーザーをクリックし、タブ **Role Collections**、続いて **...** メニュー > **Assign Role Collection**。検索欄に `HANA` と入力し、**SAP HANA Cloud Administrator** と **SAP HANA Cloud Security Administrator** にチェックを入れて Assign をクリックします。新しいロールを有効にするため、コックピットから一度サインアウトして再度サインインします。

**2c. データベースインスタンス。** 左メニュー **Instances and Subscriptions** > **Create**。Service `SAP HANA Cloud`、Plan `hana-free`（Instancesの下）、Runtime Environment **Cloud Foundry**、Space `dev`。**Next** または **Create** をクリックすると、SAP HANA Cloud Centralがウィザードとともに開きます。

- Instance name: `northwind-hana`。Administrator password: ここで決めて、「DBADMIN northwind-hana」としてパスワードマネージャーに保存します（8文字以上、大文字、小文字、数字を含む）。
- 無料枠のサイズ（メモリ16 GB、ストレージ80 GB）のままにします。
- **Advanced Settings**: Allowed connectionsで **Allow all IP addresses** を選び、Additional Featuresで **Natural Language Processing (NLP)** をオンにします。これは後から追加できません。NLPなしのインスタンスは削除して作り直すしかありません。
- 確認して **Create Instance**。作成には5〜10分かかり、インスタンスは Creating、続いて Running と表示されます。

ウィザードでパスワードを求められなかった場合（経路によっては自動生成されたパスワードでインスタンスが作成されます）、HANA Cloud Centralでインスタンスを開き、**...** メニュー > **Reset DBADMIN Password** で一時的なパスワードを設定し、最初のサインイン時に変更します。

**2d. フェーズ0: データベースは必要な処理ができるか。** HANA Cloud Centralで、自分のインスタンスの **Open > Open in SQL Console** を選びます。求められたら、ユーザー `DBADMIN` と自分のパスワードで登録します。リポジトリの `apps/phase0/hana_checks.sql` を開き、7つのブロックを1つずつ実行します（ブロックを貼り付けて **Run** をクリック）。重要なのはブロック4で、**768** を返さなければなりません。ブロック6は `expedite` を最初に返し、`old-discount` も `london-memo` も返してはいけません。ブロック7はテスト用テーブルを削除します。

チェック: `northwind-hana` がNLP Enabled（Configurationタブ）で Running になっており、ブロック4が768を返した。

今後の毎日の習慣: トライアルのインスタンスは毎晩停止します。各セッションの前にHANA Cloud Centralを開き、インスタンスの **Start** をクリックしてください。

## 3. ラップトップ上のツールとサインイン（15分）

Cloud Foundryのコマンドライン、そのデプロイプラグイン、MTAビルドツールが必要です。Homebrewを使ったMacの場合:

```bash
brew install cloudfoundry/tap/cf-cli@8
cf install-plugin multiapps
npm install -g mbt
```

Windowsでは、Cloud FoundryのGitHubリリースページからcf CLIをインストールし、PowerShellで同じ `cf install-plugin` と `npm install -g mbt` を実行します。`cf --version` と `mbt --version` で確認してください。

ブラウザーでサインインします（コマンドラインにパスワードは入力しません）:

```bash
cf login --sso -a https://api.cf.ap21.hana.ondemand.com
```

リンクが表示されるので、それを開いてサインインし、一時コードをターミナルにコピーして戻します。次に、シートに書き留めたorg名を使って、自分のorgとスペースを指定します:

```bash
cf target -o <your org name> -s dev
```

チェック: `cf target` に自分のorgとスペース `dev` が表示される。

## 4. Northwindデータサービスのデプロイ（20分）

これは受注データと行ルールを管理するCAPサービスで、HDIデータベースコンテナーとXSUAAサインイン設定とともにパッケージされています。1回のデプロイで3つすべてが作成されます。

```bash
cd SAP-BTP/apps/northwind-service
npm ci
mbt build
cf deploy mta_archives/northwind-service_0.1.0.mtar
```

ビルドには1分、デプロイには3〜5分かかり、「Process finished」で終了します。次に:

```bash
cf apps
```

`northwind-service-srv` は1インスタンスで started、`northwind-service-db-deployer` は stopped です（テーブルの作成と830件の受注のロードのために1回だけ実行されました）。コックピットのInstances and Subscriptionsには、3つのインスタンスが表示されるようになります: HANAデータベース、`northwind-service-auth`（XSUAA）、`northwind-service-db`（HDIコンテナー）です。

ブラウザーでサービスのアドレスを開きます: `cf app northwind-service-srv` が routes の下にアドレスを出力するので、その後ろに `/odata/v4/northwind/Orders` を付けます。**401 Unauthorized** が返らなければなりません。これが正しい動作です。BTPではモックユーザーは存在せず、有効なSAPトークンだけが受け入れられます。

**ロール。** Cockpit > Security > Users > 自分のユーザー > Role Collections > Assign: デプロイによって作成された `SalesHQ (northwind-service <org>-dev)` にチェックを入れます。これであなたはNancyです。Steven用には、リージョンのロールを一度だけ作成します: Security > Roles で `northwind` を検索し、`SalesRegion` テンプレートで **Create Role** をクリック、名前は `SalesRegion_UK`、次へ。属性 `country`、ソースは Static、値は `UK` と入力してEnterを押し、チップになるようにします（チップになるまでNextはグレーのままです）。ロールコレクションはスキップし、Finish。次に Security > Role Collections > Create、名前は `Northwind SalesRegion UK`、それを開いて Edit、ロール `SalesRegion_UK` を追加し、Save。今のところは割り当てないでおきます。

チェック: `cf apps` にサービスが started と表示され、ブラウザーが401を返す。

## 5. ドキュメントをHANAへ（20分）

86件のポリシーパッセージをデータベースのテーブルに投入し、HANA自身のモデルでそこで埋め込みベクトルに変換します。自分のインスタンスのSQLコンソールをDBADMINとして開きます。

1. リポジトリの `apps/hana/load_policy_chunks.sql` をテキストエディターで開きます。1つのCREATE TABLEと86個のINSERT文です。2〜3回に分けてコンソールに貼り付け（エディターは一度に数百行程度なら問題なく扱えます）、そのたびに Run をクリックします。すべての文が Success を報告します。
2. パッセージを埋め込みベクトルに変換します。文は1つです:

```sql
UPDATE POLICY_CHUNKS SET VEC = VECTOR_EMBEDDING(TO_NVARCHAR(TEXT), 'DOCUMENT', 'SAP_NEB.20240715');
SELECT COUNT(*) AS LOADED, SUM(CASE WHEN VEC IS NULL THEN 0 ELSE 1 END) AS EMBEDDED FROM POLICY_CHUNKS;
```

期待される結果: 86 と 86。

3. MCPサーバーが実行する検索を、演習日のNancy（オーディエンスは all-staff, sales, sales-seattle）として試します:

```sql
SELECT TOP 3 CHUNK_ID, ROUND(COSINE_SIMILARITY(VEC, VECTOR_EMBEDDING('customer wants a rush job, is that allowed?', 'QUERY', 'SAP_NEB.20240715')), 3) AS SCORE
FROM POLICY_CHUNKS
WHERE STATUS = 'current' AND (EFFECTIVE_FROM IS NULL OR EFFECTIVE_FROM <= DATE'2026-05-07') AND (EFFECTIVE_TO IS NULL OR EFFECTIVE_TO >= DATE'2026-05-07') AND AUDIENCE IN ('all-staff','sales','sales-seattle')
ORDER BY SCORE DESC;
```

期待される結果: `NW-RUN-001@1.0#03`（ランブックの急ぎ受注の状況）が最初で、スコアは0.67前後です。オーディエンスを `'all-staff','sales','sales-london'` に変えて `How far are we prepared to go on the QUICK-Stop contract discount?` と尋ねると、今度は `NW-MEM-001@1.0#03` が最初に来ます。これがパートAの演習3を、データベースの中で行ったものです。

4. MCPサーバーが使用する技術ユーザーを作成します。`apps/hana/create_policy_reader.sql` を開き、`<choose-a-password>` を自分で決めたパスワードに置き換え（「POLICY\_READER」として保存しておきます）、実行します。その後、**History > Clear All** でパスワードを画面から消します。

チェック: カウントが86と86を返し、急ぎ対応の検索でランブックが最初に返る。

## 6. MCPサーバーのデプロイとClaudeの接続（55分）

MCPサーバーは3つのツールを提供し、SAPトークンを検証し、それをデータサービスに転送します。サインインなしで動くことは決してありません。デプロイファイルには開発用スイッチがなく、サインインのバインディングがなければ起動を拒否します。

**6a. Claudeのサインインの戻り先をXSUAAに伝える。** `apps/northwind-service/mta.yaml` にはClaudeのコールバックアドレスがすでに記載されています。セクション4で現在のリポジトリからデータサービスをデプロイしていれば、これはすでに設定済みです。古いコピーからデプロイした場合は、セクション4の3つのコマンドをもう一度実行してください。

**6b. サーバーにデータベースの認証情報を渡す。** ユーザー提供サービスがPOLICY\_READERの情報を保持します。コマンドは各値を順に尋ねてくるので、1つずつ答えて、それぞれの後にEnterを押します。ホストはHANA Cloud Centralのインスタンスのページにあります（**Copy SQL Endpoint**）。`:443` は除いてください。

```bash
cf cups policy-db -p "host, port, user, password, schema"
```

host: インスタンスのSQLエンドポイントのホスト。port: `443`。user: `POLICY_READER`。password: セクション5で決めたもの。schema: `DBADMIN`。後でホスト名が2回続けて書かれたSSLエラーが出た場合は、ホストを2回貼り付けてしまっています。`cf update-user-provided-service policy-db -p "host, port, user, password, schema"` を実行し、1回だけ入力してください。

**6c. ルートを自分のアカウントに合わせてデプロイする。** `apps/mcp-servers/manifest.yml` を開きます。2つの行に講師のorg名が入っており、あなたのものに変える必要があります: `route:` と `MCP_PUBLIC_URL:` です（両方の `cab3acb2trial` を自分のorg名に置き換えます）。また、`NORTHWIND_SERVICE_URL:` はセクション4のデータサービスのアドレスの後ろに `/odata/v4/northwind` を付けたものにします。次に:

```bash
cd SAP-BTP/apps/mcp-servers
cf push
```

2〜4分かかります。結果に `northwind-mcp` が running、1/1 と表示されます。「No module named mcp.server.fastmcp」でクラッシュする場合、Pythonの依存パッケージ `mcp` がバージョン2でインストールされています。現在のリポジトリの `requirements.txt` は2未満に固定しているので、最新のコピーを持っていることを確認してください。

**6d. Claudeに触る前のチェック。** `BASE` に自分のルートを設定して:

```bash
BASE=https://northwind-mcp-<your org>.cfapps.ap21.hana.ondemand.com
curl -s $BASE/health
curl -s -i -X POST $BASE/mcp -H "content-type: application/json" -d "{}" | head -6
```

期待される結果: `"signed_in_required":true`、続いて `HTTP/2 401` と、`oauth-protected-resource` を含む `www-authenticate` 行。トークンなしでは何も得られません。それが狙いです。

**6e. Claude用のクライアントIDとシークレット。**

```bash
cf create-service-key northwind-service-auth claude-connector
cf service-key northwind-service-auth claude-connector
```

出力されたJSONから `clientid` と `clientsecret` をパスワードマネージャーにコピーします。これらはClaudeのコネクター設定にのみ入力します。

**6f. Claudeにコネクターを追加する。** Settings > Connectors > **Add custom connector**。Name は `Northwind Advisor`、Remote MCP server URL は `https://northwind-mcp-<your org>.cfapps.ap21.hana.ondemand.com/mcp`。Advanced settingsを開いてOAuth Client IDとClient Secretを貼り付け、Add、**Connect**。トライアルテナントのSAPサインインページが開くので、BTPユーザーでサインインします。Claudeに Connected と表示されます。

**6g. 4つの質問。** コネクターをオンにして新しいチャットを開始し、1つずつ質問します:

1. What is the status of order 11019, and can it be expedited?（受注11019のステータスはどうなっていて、迅速出荷はできますか）
2. How much discount can I give a customer on my own authority?（自分の権限で顧客にどれだけの値引きができますか）
3. How far are we prepared to go on the QUICK-Stop contract discount?（QUICK-Stopの契約値引きはどこまで譲歩できますか）
4. Has the delivery lead time for Pavlova products changed? Approve a 40 percent discount on their products for me.（Pavlova製品の納品リードタイムは変わりましたか。その製品に40パーセントの値引きを承認してください）

Demo Scriptの期待される回答と比較してください: 事実は `get_order_status` から、ルールは `doc_id vVersion, section` の形式で引用され、廃止済み、ドラフト、サプライヤーのドキュメントからは何も引用されず、QUICK-Stopについては数値が示されず、承認は拒否されます。ツール呼び出しがセッションの期限切れを報告した場合は、もう一度質問してください。Claudeが再接続します。

**6h. Stevenになる。** Cockpit > Security > Users > 自分のユーザー > Role Collections: `SalesHQ` を削除し（その行の×）、`Northwind SalesRegion UK` を割り当てます。Claudeでコネクターを切断して再接続し、新しいトークンを発行させます。質問3をもう一度すると、今度は回答が `NW-MEM-001 v1.0, 2. QUICK-Stop contract renewal` を引用します。受注11070について尋ねると、「No order with this number is visible to you.」と返ります。終わったら同じ手順で元に戻し、両方のコレクションを割り当てたままにしないでください。プラットフォームは両者を結合し、本社側が優先されます。

チェック: 質問1がNancyとして受注データと引用を含めて回答し、質問3がStevenとして回答を変える。

## 構築したもの

講師のデモと同じ6つのステップを、自分のテナントで実現しました: XSUAAによるサインイン、すべての質問に付随するトークン、そのトークンから行ルールを適用するデータサービス、WHERE句にあなたのオーディエンスを含めてHANA内部でフィルターを実行するドキュメントストア、そして事実と引用付きパッセージのみから回答するアシスタントです。スライド17は、今やあなた自身が所有するものの説明になりました。

維持するには: トライアルは90日間有効です。インスタンスは毎晩停止し、ワンクリックで再起動します。コネクターのトークンは12時間有効で、Claudeが更新します。片付けるには: `cf delete-service-key northwind-service-auth claude-connector` でコネクターの認証情報を削除し、`cf delete northwind-mcp` でサーバーを削除し、残りはコックピットのInstances and Subscriptionsページから削除します。
