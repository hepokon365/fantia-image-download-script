# fantia-image-download-script

ファンティア(Fantia)のファンクラブに投稿された、画像ファイルを一括でダウンロードするPythonスクリプトです。

## 動作検証済み環境

* Python: 3.8.5

## 利用方法

1. `pip install -r requirements.txt` を実行
1. ブラウザでファンティアにログイン
1. `fantia_image_download.ini` の変更
    * ブラウザクッキーの `_session_id` の値を、 `session_id=` の後ろに記述
    * ダウンロードしたいファンクラブのIDを、 `fan_club_id=` の後ろに記述
1. `python fantia_image_download.py` を実行
    * `fantia_image_download.ini` の `download_root_dir` で指定したディレクトリ配下に、 `<fan_club_id>/<posts_id>_<posted_date>_<posted_time>/` という名前で投稿ごとにディレクトリが作成され、その中に画像がダウンロードされます

## 免責事項

* 本スクリプトの作成者は、株式会社虎の穴、ファンティア、ならびにファンティア開発に一切関係はありません。
* 本スクリプトは、[ファンティア利用規約](https://fantia.jp/help/terms)に違反のない範囲にて、自己責任でご利用ください。
  * ファンティアへの投稿のダウンロード可否については、[ヘルプページ](https://help.fantia.jp/1279)にて可能と回答されております。
* 本スクリプトの作成者は、本スクリプトによって生じた損害等について、一切の責任を負いかねますのでご了承ください。
