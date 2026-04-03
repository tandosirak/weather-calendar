import os
import requests
import pytz
from datetime import datetime, timedelta
from icalendar import Calendar, Event

# --- [설정] ---
NX, NY = 60, 127              # 서울 격자 좌표
REG_ID_TEMP = '11B10101'      # 중기기온 구역 (서울)
REG_ID_LAND = '11B00000'      # 중기육상 구역 (서울/인천/경기도)
API_KEY = os.environ.get('KMA_API_KEY')

def get_emoji(wf_or_sky, pty='0'):
    """날씨 상태를 이모지로 변환"""
    wf = str(wf_or_sky)
    if '비' in wf or '소나기' in wf: return "🌧️"
    if '눈' in wf: return "🌨️"
    if '구름많음' in wf: return "⛅"
    if '흐림' in wf: return "☁️"
    if '맑음' in wf or wf == '1': return "☀️"
    if pty != '0': return "🌧️"
    if wf == '3': return "⛅"
    if wf == '4': return "☁️"
    return "🌡️"

def fetch_api(url):
    try:
        res = requests.get(url)
        if res.status_code == 200:
            return res.json()
        print(f"API 응답 에러({res.status_code}): {res.text}")
        return None
    except Exception as e:
        print(f"네트워크 에러: {e}")
        return None

def main():
    seoul_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_tz)
    cal = Calendar()
    cal.add('X-WR-CALNAME', '기상청 날씨 달력')
    
    # 1. 단기예보 (0~3일) - getVilageFcst 사용
    base_date = now.strftime('%Y%m%d')
    pub_hours = [2, 5, 8, 11, 14, 17, 20, 23]
    base_h = max([h for h in pub_hours if h <= now.hour], default=2)
    base_time = f"{base_h:02d}00"
    
    url_short = f"https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getVilageFcst?pageNo=1&numOfRows=1000&dataType=JSON&base_date={base_date}&base_time={base_time}&nx={NX}&ny={NY}&authKey={API_KEY}"
    
    forecast_map = {}
    data = fetch_api(url_short)
    if data and 'response' in data and 'body' in data['response']:
        items = data['response']['body']['items']['item']
        for it in items:
            d, t, cat, val = it['fcstDate'], it['fcstTime'], it['category'], it['fcstValue']
            if d not in forecast_map: forecast_map[d] = {}
            if t not in forecast_map[d]: forecast_map[d][t] = {}
            forecast_map[d][t][cat] = val

    # 2. 중기예보 (4~10일) - getMidTa, getMidLandFcst 사용
    tm_fc = now.strftime('%Y%m%d') + ("0600" if now.hour < 18 else "1800")
    url_mid_temp = f"https://apihub.kma.go.kr/api/typ02/openApi/MidFcstInfoService/getMidTa?dataType=JSON&regId={REG_ID_TEMP}&tmFc={tm_fc}&authKey={API_KEY}"
    url_mid_land = f"https://apihub.kma.go.kr/api/typ02/openApi/MidFcstInfoService/getMidLandFcst?dataType=JSON&regId={REG_ID_LAND}&tmFc={tm_fc}&authKey={API_KEY}"
    
    mid_temp_data = fetch_api(url_mid_temp)
    mid_land_data = fetch_api(url_mid_land)
    
    mid_map = {}
    if mid_temp_data and mid_land_data:
        try:
            t_item = mid_temp_data['response']['body']['items']['item'][0]
            l_item = mid_land_data['response']['body']['items']['item'][0]
            for i in range(4, 11):
                d_str = (now + timedelta(days=i)).strftime('%Y%m%d')
                suffix = "Am" if i <= 7 else ""
                mid_map[d_str] = {
                    'min': t_item.get(f'taMin{i}'),
                    'max': t_item.get(f'taMax{i}'),
                    'wf': l_item.get(f'wf{i}{suffix}'),
                    'rn': l_item.get(f'rnSt{i}{suffix}')
                }
        except: pass

    # 3. 캘린더 일정 생성
    for i in range(11):
        target_dt = now + timedelta(days=i)
        d_str = target_dt.strftime('%Y%m%d')
        event = Event()
        
        if d_str in forecast_map: # 0~3일차
            day_data = forecast_map[d_str]
            times = sorted(day_data.keys())
            tmps = [float(day_data[t]['TMP']) for t in times if 'TMP' in day_data[t]]
            t_min, t_max = (min(tmps), max(tmps)) if tmps else (0, 0)
            mid_t = "1200" if "1200" in day_data else times[len(times)//2]
            rep_em = get_emoji(day_data[mid_t].get('SKY'), day_data[mid_t].get('PTY'))
            event.add('summary', f"{rep_em} {int(t_min)}° / {int(t_max)}°")
            desc = [f"[{t[:2]}시] {get_emoji(day_data[t].get('SKY'), day_data[t].get('PTY'))} {day_data[t].get('TMP')}°C, ☔{day_data[t].get('POP')}%" for t in times]
            event.add('description', "\n".join(desc))
        elif d_str in mid_map: # 4~10일차
            m = mid_map[d_str]
            event.add('summary', f"{get_emoji(m['wf'])} {m['min']}° / {m['max']}°")
            event.add('description', f"날씨: {m['wf']}\n강수확률: {m['rn']}%")

        event.add('dtstart', target_dt.date())
        event.add('dtend', (target_dt + timedelta(days=1)).date())
        cal.add_component(event)

    with open('weather.ics', 'wb') as f:
        f.write(cal.to_ical())
    print("✅ 10일치 날씨 데이터 업데이트 완료!")

if __name__ == "__main__":
    main()
