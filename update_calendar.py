import os
import requests
import pytz
from datetime import datetime, timedelta
from icalendar import Calendar, Event

# --- [1. 설정] ---
NX, NY = 60, 127
LOCATION_NAME = "봉화산로 193"
API_KEY = os.environ.get('KMA_API_KEY')

def get_emoji(sky, pty):
    sky, pty = str(sky), str(pty)
    if pty != '0':
        if pty in ['1', '4']: return "🌧️"
        if pty == '2': return "🌨️"
        if pty == '3': return "❄️"
    if sky == '1': return "☀️"
    if sky == '3': return "⛅"
    if sky == '4': return "☁️"
    return "🌡️"

def main():
    seoul_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_tz)
    cal = Calendar()
    cal.add('X-WR-CALNAME', '기상청 날씨')
    cal.add('X-WR-TIMEZONE', 'Asia/Seoul')

    # 단기예보 호출 (4.3 단기예보조회)
    base_date = now.strftime('%Y%m%d')
    # 가장 최근 발표된 예보를 가져옵니다 (0200, 0500, 0800 등)
    pub_hours = [2, 5, 8, 11, 14, 17, 20, 23]
    base_h = max([h for h in pub_hours if h <= now.hour], default=2)
    base_time = f"{base_h:02d}00"
    
    url = f"https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getVilageFcst?dataType=JSON&base_date={base_date}&base_time={base_time}&nx={NX}&ny={NY}&numOfRows=1000&authKey={API_KEY}"
    
    forecast_map = {}
    try:
        res = requests.get(url).json()
        items = res['response']['body']['items']['item']
        for it in items:
            d, t, cat, val = it['fcstDate'], it['fcstTime'], it['category'], it['fcstValue']
            if d not in forecast_map: forecast_map[d] = {}
            if t not in forecast_map[d]: forecast_map[d][t] = {}
            forecast_map[d][t][cat] = val
    except:
        print("데이터를 가져오는 데 실패했습니다.")

    # 11일치 달력 생성
    for i in range(11):
        target_dt = now + timedelta(days=i)
        d_str = target_dt.strftime('%Y%m%d')
        event = Event()
        
        # 기상청이 제공한 3일치 상세 데이터가 있는 경우
        if d_str in forecast_map:
            d_data = forecast_map[d_str]
            times = sorted(d_data.keys())
            tmps = [float(d_data[t]['TMP']) for t in times if 'TMP' in d_data[t]]
            
            if tmps:
                t_min, t_max = int(min(tmps)), int(max(tmps))
                mid_t = "1200" if "1200" in d_data else times[len(times)//2]
                rep_em = get_emoji(d_data[mid_t].get('SKY', '1'), d_data[mid_t].get('PTY', '0'))
                
                # 제목: 이미지 스타일
                event.add('summary', f"{rep_em} {t_min}°C / {t_max}°C")
                
                # 본문: 이미지 스타일 (위치 + 시간대별 상세)
                desc = [f"📍 {LOCATION_NAME}\n"]
                for t in times:
                    it = d_data[t]
                    em = get_emoji(it.get('SKY', '1'), it.get('PTY', '0'))
                    tmp = it.get('TMP', '0')
                    pop = it.get('POP', '0')
                    reh = it.get('REH', '0')
                    wsd = it.get('WSD', '0')
                    desc.append(f"[{t[:2]}h] {em} {tmp}°C (☔{pop}% 💧{reh}% 💨{wsd}m/s)")
                
                desc.append(f"\nLast update: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                event.add('description', "\n".join(desc))
            else:
                event.add('summary', "⛅ 상세 예보 준비중")
        
        # 데이터가 없는 4일차 이후 (중기 예보 영역)
        else:
            event.add('summary', "⛅ 중기 예보 확인")
            event.add('description', "4일차 이후 예보는 기상청 중기예보를 참조하세요.")

        event.add('dtstart', target_dt.date())
        event.add('dtend', (target_dt + timedelta(days=1)).date())
        event.add('uid', f"{d_str}@kma_weather")
        cal.add_component(event)

    with open('weather.ics', 'wb') as f:
        f.write(cal.to_ical())
    print("✅ 3일치 상세 데이터 포함 업데이트 완료!")

if __name__ == "__main__":
    main()
