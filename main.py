import os
import random
import time
import csv
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# [환경 설정]
USER_DATA_DIR = os.getenv("USER_DATA_DIR")
START_URL = os.getenv("START_URL")
BLACKLIST = ["キーワード1", "キーワード2"]

def run_scrapper():
    # 1. 초기 설정
    final_results = [] 
    count = 0
    limit = 300 # 수집 목표 개수 설정

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR, 
            headless=False,
            args=["--start-maximized"]
        )
        page = context.new_page()

        # 2. 로그인 세션 확인
        print("[!] 로그인 확인 단계입니다.")
        page.goto("https://doda.jp/auth/login/")
        input(">> 로그인이 확인되었다면 Enter를 누르세요 (중단 시 Ctrl+C): ")

        # 3. 검색 결과 페이지 이동
        print(f"[*] 페이지 이동 시작: {START_URL}")
        try:
            page.goto(START_URL, wait_until="commit", timeout=60000)
            time.sleep(7) # 페이지 안정화 대기
        except Exception as e:
            print(f"[*] 이동 중 통신 재설정 발생(무시하고 진행)")

        try:
            while True:
                # 공고 목록 로딩 대기
                try:
                    page.wait_for_selector("article, .cl_jobListUnit", timeout=15000)
                except:
                    print("[!] 공고 요소를 더 이상 찾을 수 없습니다.")
                    break

                job_units = page.query_selector_all("article, .cl_jobListUnit")
                print(f"\n[*] 현재 페이지 공고 {len(job_units)}개 검사 중... (현재 수집: {count}/{limit})")

                for unit in job_units:
                    # 목표 수치 도달 시 즉시 중단
                    if count >= limit:
                        break

                    detail_page = None
                    try:
                        # 상세 페이지 링크 추출
                        link_elem = unit.query_selector("a.jobTitleLink, a")
                        if not link_elem: continue
                        
                        detail_url = link_elem.get_attribute("href")
                        if not detail_url: continue
                        if detail_url.startswith("/"):
                            detail_url = "https://doda.jp" + detail_url
                        
                        # --- [여기가 수정된 포인트!] ---
                        # 상세 페이지를 열기 전에 1.5초 ~ 3초 사이로 무작위 대기 (인간미 추가)
                        wait_time = random.uniform(1.5, 3.0)
                        print(f"[*] 인간미 추가: {wait_time:.2f}초 대기 후 접속...")
                        time.sleep(wait_time)
                        # ------------------------------

                        # 상세 페이지 이동 및 검사
                        detail_page = context.new_page()
                        detail_page.goto(detail_url, wait_until="domcontentloaded")
                        time.sleep(2) 
                        
                        content = detail_page.content()
                        
                        # 블랙리스트 필터링
                        if any(kw in content for kw in BLACKLIST):
                            print(f"[-] 제외: {detail_url.split('/')[-2]}")
                            detail_page.close()
                            continue
                        
                        # [제목 수집 로직]
                        title = "제목 없음"
                        selectors = [
                            ".jobSearchDetail-heading__title",
                            "p.jobSearchDetail-heading__title",
                            "h1",
                            ".jobSearchDetail-heading h1"
                        ]
                        
                        for selector in selectors:
                            title_elem = detail_page.query_selector(selector)
                            if title_elem:
                                temp_title = title_elem.inner_text().strip()
                                if temp_title and "関連情報" not in temp_title and "転職" not in temp_title:
                                    title = temp_title
                                    break
                        
                        # 유효한 공고인 경우 저장 및 카운트 증가
                        final_results.append({"title": title, "url": detail_url})
                        count += 1
                        print(f"[+] ({count}/{limit}) 수집 성공: {title}")
                        
                        detail_page.close()
                        
                    except Exception as e:
                        if detail_page: detail_page.close()
                        continue

                # 목표 수치 도달 여부 다시 확인 후 루프 탈출
                if count >= limit:
                    print(f"\n[*] 목표치 {limit}개 수집 완료. 프로그램을 종료합니다.")
                    break

                # 다음 페이지 페이징 처리 (페이지 전환 전에도 살짝 쉬어주면 좋습니다)
                next_button = page.query_selector("a:has-text('次へ'), .next a")
                if next_button:
                    print("[*] 다음 페이지로 이동합니다...")
                    time.sleep(random.uniform(2, 4)) # 페이지 전환 전 2~4초 휴식
                    next_button.click()
                    time.sleep(5)
                else:
                    print("[*] 마지막 페이지입니다.")
                    break

        except KeyboardInterrupt:
            print("\n[!] 사용자에 의해 수집이 중단되었습니다. 현재까지의 데이터를 저장합니다.")
        
        finally:
            save_to_csv(final_results)
            context.close()

def save_to_csv(data):
    if not data:
        print("[!] 저장할 데이터가 없습니다.")
        return
    
    import time
    filename = f'doda_filtered_{int(time.time())}.csv'
    keys = data[0].keys()
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(data)
        
    print(f"\n" + "="*50)
    print(f"[*] 총 {len(data)}개의 결과가 저장되었습니다.")
    print(f"[*] 파일명: {filename}")
    print("="*50)

if __name__ == "__main__":
    run_scrapper()