---
title: "AIユースケース一覧 (Dataview)"
---

# AIユースケース一覧

```dataview
TABLE
  summary AS 概要,
  category AS カテゴリ,
  industry AS 業界,
  status AS ステータス,
  github_link AS GitHub,
  contributors AS コントリビューター,
  tags AS タグ
FROM "use-cases"
WHERE file.name != "0_DB_AI_usecase" AND file.name != "0_DView_list"
SORT createdAt DESC
```

このファイルはDataviewプラグインを使用して、`use-cases`フォルダ内のAIユースケースを一覧表示します。
ウェブ公開時など、DB Folderプラグインが利用できない環境での利用を想定しています。
