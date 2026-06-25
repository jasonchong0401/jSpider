#!/usr/bin/env python3
"""
Investing.com Commodities Scraper
使用 Playwright + stealth 从 Investing.com 抓取商品数据

用法:
    python scrape_commodities.py                    # 抓取所有商品
    python scrape_commodities.py --energy           # 只抓能源
    python scrape_commodities.py --metals           # 只抓金属
    python scrape_commodities.py --agriculture      # 只抓农产品
    python scrape_commodities.py --output data.csv  # 保存为 CSV

需要在本地运行（Investing.com 会封数据中心 IP）
"""

import asyncio
import json
import csv
import sys
import argparse
from datetime import datetime
from pathlib import Path

# ============================================================
# 配置
# ============================================================
CATEGORY_URLS = {
    "all": "https://www.investing.com/commodities/",
    "energy": "https://www.investing.com/commodities/energies",
    "metals": "https://www.investing.com/commodities/metals",
    "agriculture": "https://www.investing.com/commodities/agricultural",
}

CATEGORY_SECTIONS = {
    "energy": ["Crude Oil", "Brent Oil", "Natural Gas", "Gasoline", "Heating Oil"],
    "metals": ["Gold", "Silver", "Copper", "Platinum", "Palladium"],
    "agriculture": ["Corn", "Soybeans", "Wheat", "Coffee", "Sugar", "Cotton"],
}

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Investing.com Commodities Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", default=True, help="所有商品 (默认)")
    group.add_argument("--energy", action="store_true", help="能源")
    group.add_argument("--metals", action="store_true", help="金属")
    group.add_argument("--agriculture", action="store_true", help="农产品")
    parser.add_argument("--output", type=str, help="输出文件路径 (.json 或 .csv)")
    parser.add_argument("--headless", action="store_true", default=True, help="无头模式 (默认)")
    parser.add_argument("--visible", action="store_true", help="显示浏览器窗口")
    parser.add_argument("--timeout", type=int, default=30, help="页面加载超时秒数 (默认 30)")
    parser.add_argument("--retries", type=int, default=2, help="失败重试次数 (默认 2)")
    return parser.parse_args()


def get_url(args):
    if args.energy:
        return CATEGORY_URLS["energy"], "energy"
    elif args.metals:
        return CATEGORY_URLS["metals"], "metals"
    elif args.agriculture:
        return CATEGORY_URLS["agriculture"], "agriculture"
    return CATEGORY_URLS["all"], "all"


def extract_commodity_data(page):
    """从页面提取商品数据"""
    return page.evaluate("""
        () => {
            const results = [];
            const seen = new Set();

            // 策略1: 找 datatable
            const table = document.querySelector('table[class*="datatable"], table.genTbl');
            const rows = table
                ? table.querySelectorAll('tbody tr')
                : document.querySelectorAll('table tbody tr');

            for (const row of rows) {
                const cells = row.querySelectorAll('td');
                if (!cells.length) continue;

                const texts = [];
                cells.forEach(c => {
                    let t = (c.innerText || c.textContent || '').trim();
                    // 清理多余空格和换行
                    t = t.replace(/\\s+/g, ' ').trim();
                    texts.push(t);
                });

                // 跳过表头行
                const first = texts[0] || '';
                if (!first || first.length > 120) continue;
                if (/Name|Symbol|Instrument|Sort/i.test(first)) continue;
                if (/Sponsored|Advertisement/i.test(first)) continue;

                // 去重
                const key = first.substring(0, 40).toLowerCase();
                if (seen.has(key)) continue;
                seen.add(key);

                results.push({
                    name: first,
                    last: texts[1] || '',
                    high: texts[2] || '',
                    low: texts[3] || '',
                    change: texts[4] || '',
                    change_pct: texts[5] || '',
                    time: texts[6] || '',
                });
            }

            // 策略2: 如果上面没找到，尝试 React datatable
            if (!results.length) {
                const allRows = document.querySelectorAll(
                    '[data-test="datatable-row"], [class*="datatable_row"], [class*="row"]'
                );
                for (const row of allRows) {
                    const tds = row.querySelectorAll('td, [class*="cell"]');
                    if (tds.length < 3) continue;
                    const texts = [];
                    tds.forEach(c => texts.push((c.innerText || c.textContent || '').trim().replace(/\\s+/g, ' ')));
                    if (texts[0] && texts[0].length < 120) {
                        results.push({
                            name: texts[0],
                            last: texts[1] || '',
                            high: texts[2] || '',
                            low: texts[3] || '',
                            change: texts[4] || '',
                            change_pct: texts[5] || '',
                            time: texts[6] || '',
                        });
                    }
                }
            }

            return results;
        }
    """)


async def scrape_once(browser, url, timeout):
    """单次抓取"""
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        timezone_id="America/New_York",
    )

    page = await context.new_page()

    # 反检测脚本
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };
    """)

    try:
        await page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
        title = await page.title()

        # 检测 Cloudflare
        if "Just a moment" in title or "Cloudflare" in title:
            print(f"  ⚠️  Cloudflare 拦截，等待自动验证...")
            for i in range(20):
                await page.wait_for_timeout(3000)
                title = await page.title()
                if "Just a moment" not in title and "Cloudflare" not in title:
                    print(f"  ✓ 验证通过 (等待 {(i+1)*3}s)")
                    break
                if i % 5 == 4:
                    print(f"     仍在等待... ({(i+1)*3}s)")

        # 等待数据表加载
        try:
            await page.wait_for_selector('table', timeout=15000)
        except:
            pass

        await page.wait_for_timeout(3000)

        # 滚动触发懒加载
        await page.evaluate("window.scrollTo(0, 600)")
        await page.wait_for_timeout(2000)

        data = await extract_commodity_data(page)
        return data, await page.title()

    finally:
        await context.close()


async def main():
    args = parse_args()
    url, category = get_url(args)
    headless = not args.visible

    print(f"{'='*60}")
    print(f"  Investing.com Commodities Scraper")
    print(f"  目标: {url}")
    print(f"  类别: {category}")
    print(f"  模式: {'可见' if not headless else '无头'}")
    print(f"{'='*60}\n")

    # 动态导入 Playwright（不在服务器上加载）
    from playwright.async_api import async_playwright
    import playwright_stealth

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )

        data = []
        for attempt in range(args.retries + 1):
            if attempt > 0:
                print(f"\n  重试 {attempt}/{args.retries}...")
                await asyncio.sleep(3)

            try:
                data, title = await scrape_once(browser, url, args.timeout)
                print(f"  页面标题: {title}")
                print(f"  抓取到 {len(data)} 条数据\n")

                if data:
                    break
                elif attempt < args.retries:
                    print(f"  没有数据，重试中...")
            except Exception as e:
                print(f"  错误: {e}")
                if attempt < args.retries:
                    print(f"  重试中...")

        await browser.close()

    if not data:
        print("\n  ❌ 未能获取任何数据。")
        print("  可能原因:")
        print("    1. Investing.com 页面结构变化")
        print("    2. 网络问题或被防火墙拦截")
        print("    3. 需要更长的超时时间 (--timeout 60)")
        print("\n  建议: 试试 --visible 模式查看浏览器实际情况")
        return 1

    # 打印结果
    print(f"  {'商品名称':<25} {'最新价':>12} {'涨跌':>10} {'涨跌幅':>8} {'时间':>12}")
    print(f"  {'-'*25} {'-'*12} {'-'*10} {'-'*8} {'-'*12}")
    for item in data:
        chg = item.get("change", "") or ""
        chg_pct = item.get("change_pct", "") or ""
        print(
            f"  {item['name']:<25} "
            f"{item['last']:>12} "
            f"{chg:>10} "
            f"{chg_pct:>8} "
            f"{item.get('time', ''):>12}"
        )

    # 保存到文件
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.output:
        outpath = Path(args.output)
    else:
        outpath = OUTPUT_DIR / f"commodities_{category}_{ts}.json"

    outpath.parent.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = outpath.with_suffix(".json")
    json_path.write_text(
        json.dumps(
            {
                "source": url,
                "category": category,
                "scraped_at": datetime.now().isoformat(),
                "count": len(data),
                "data": data,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # CSV
    csv_path = outpath.with_suffix(".csv")
    if data:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["name", "last", "high", "low", "change", "change_pct", "time"],
            )
            writer.writeheader()
            writer.writerows(data)

    print(f"\n  ✓ {len(data)} 条数据已保存:")
    print(f"    JSON: {json_path}")
    print(f"    CSV:  {csv_path}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
