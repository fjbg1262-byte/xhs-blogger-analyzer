CHAPTER 04 / GET IT
INSTALL + USE

—— 装它，用它

两行装好，一行跑起来。

bash

git clone https://github.com/fjbg1262-byte/xhs-blogger-analyzer
cd xhs-blogger-analyzer && npm install && pip install -r requirements.txt


用法一：Claude Code（推荐）

/xhs-blogger-deep-research

然后按引导提供博主 URL + Cookie，剩下全自动。


用法二：命令行分步跑

node scrape.js --url <博主URL> --cookies cookies.json --output ./data
python analyze_all.py --notes ./data/all_notes.json --output ./data/results.json
python generate_reports.py --input ./data/results.json --output ./reports


需要什么
Node.js 18+ · Python 3.8+ · Chrome（Playwright 自动装）

小红书号: fjbg1262
