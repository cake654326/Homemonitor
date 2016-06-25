#!/usr/bin/env python
# -*- coding: utf-8 -*-

#=======CONFIGURE============================================
APIKEY_MAILGUN = "key-090bdff9e11f02225c3911dd68ae4666"
API_MAILGUN_DOMAIN = "mg.appflying.net"

#-for mode 1 ---------------------
tvList = ["wav/tv/tv1.wav", "wav/tv/tv2.wav", "wav/tv/tv3.wav", "wav/tv/tv4.wav", "wav/tv/tv5.wav", "wav/tv/tv6.wav", "wav/tv/tv7.wav"]

PIR_sleep_PictureAgainPeriod = 30  #要休息幾秒再度開始一輪的拍攝
PIR_sleep_take_2_PicturesPeriod = 0.5  #拍攝每張相片的間隔時間

modeSecutirt_waittime = 300  # 180, 300, 600, 900 設定外出模式後. 幾秒後才會開始動作.
#-for all mode ------------------------------
ENV_checkPeriod = 300  #幾秒要偵測一次溫溼度等環境值


##蘋果日報-財經總覽 "http://www.appledaily.com.tw/rss/newcreate/kind/sec/type/8"
##蘋果日報-頭條 "http://www.appledaily.com.tw/rss/newcreate/kind/sec/type/1077"
##聯合報-要聞 "http://udn.com/udnrss/BREAKINGNEWS1.xml"
##聯合報-財經 "http://udn.com/udnrss/BREAKINGNEWS6.xml"
##聯合報-財經焦點 "http://udn.com/udnrss/financesfocus.xml"
##天下雜誌 "http://www.cw.com.tw/RSS/cw_content.xml"
##自由時報-頭版 "http://news.ltn.com.tw/rss/focus.xml"
##自由時報-財經 "http://news.ltn.com.tw/rss/business.xml"
##中央氣象局警報、特報 "http://www.cwb.gov.tw/rss/Data/cwb_warning.xml"
##商業周刊 - 最新綜合文章 "http://bw.businessweekly.com.tw/feedsec.php?feedid=0"
##國民健康署 » 新聞 "http://www.hpa.gov.tw/Bhpnet/Handers/RSSHandler.ashx?c=news"
##NEWSREPORT_URL = "http://www.appledaily.com.tw/rss/newcreate/kind/sec/type/1077"
##NEWSREPORT_SPEAKER = "MCHEN_Bruce"

# ---------------------------------->尚待完成
#A1:目前時間 A2:靜思語 A3:外面天氣 A4:室內狀況 A5:新聞播報 A6:今日預約提醒 A7:明日預約提醒 A8:未來預約提醒 A80:開頭語 A99:結語
#schedule_workingDay = [ {"time": "07:15", "action": ["A80", "A2", "A4", "A3", "A5", "A6"]}, {"time":"12:00", "action": ["A80", "A4", "A3", "A2"]}, {"time":"18:30", "action": ["A1","A4","A3","A2","A7","A8"]} ]
#schedule_offDay = [ {"time":"11:30", "action": ["A4","A3","A6"] } ]

#S1:播放音樂  S2:播放電視  S3:播放錄音人聲
#schedule_security = [ {"time":"09:30", "action":["S1", "S3"]}, {"time":"12:30", "action": ["S2"]}, {"time":"18:00", "action": ["S2"]}. {"time":"21:30","action":["S1","S2","S3"]} ]
#<--------------------------------------


#======MODULES================================================
import RPi.GPIO as GPIO
import os, sys
from subprocess import call
import requests
import mcp3008
import time
import Adafruit_DHT as dht
import logging, random
import picamera
import speechClass
import urllib
import json

# Cloudinary ---------------------------
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
from cloudinary.api import delete_resources_by_tag, resources_by_tag

#=====SYSTEM===================================================
reload(sys)
sys.setdefaultencoding('utf8')

camera = picamera.PiCamera()
camera.sharpness = 0
camera.contrast = 0
camera.brightness = 50
camera.saturation = 0
camera.ISO = 0
camera.video_stabilization = False
camera.exposure_compensation = 0
camera.exposure_mode = 'auto'
camera.meter_mode = 'average'
camera.awb_mode = 'auto'
camera.image_effect = 'none'
camera.color_effects = None
camera.rotation = 0
camera.hflip = False
camera.vflip = True
camera.crop = (0.0, 0.0, 1.0, 1.0)

pinPIR = 35
pinDHT22 = 13
pinLED_RED = 38
pinLED_BLUE = 36
pinLED_YELLOW = 40
pinBTN_Security = 32

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(pinBTN_Security, GPIO.IN, pull_up_down=GPIO.PUD_UP) #使用內建的上拉電阻

GPIO.setup(pinPIR ,GPIO.IN)
GPIO.setup(pinLED_RED ,GPIO.OUT)
GPIO.setup(pinLED_YELLOW ,GPIO.OUT)
GPIO.setup(pinLED_BLUE ,GPIO.OUT)

os.chdir(os.path.join(os.path.dirname(sys.argv[0]), '.'))  # for Cloudinary

logger = logging.getLogger('msg')
hdlr = logging.FileHandler('/home/pi/monitor/msg.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)

PIR_last_pictureTime = time.time()  #上次拍攝相片時間

ENV_warning_repeat_period = 120  #相同的警示提示音, 要間隔多少秒再提醒一次
ENV_lastwarningtime = 0  #上次警示提示音的時間

ENV_lstchecktime = 0  #上次偵測環境值的時間

modeOperation = 0  # 0 -> 儲存目前的運作模式, 一般模式  1 -> 外出模式
modeSecutiry_starttime = 0  #儲存外出模式的開始時間, 預設在 modeSecutirt_waittime 後才開始動作

lastHourlySchedule = 999 #上次每小時固定執行工作的執行時間(小時)
btn_secutiry_lastclicktime = 0   #上次按按鈕的時間, 以避免多次觸發

#===Functions===========================================================

def is_json(myjson):
	try:
		json_object = json.loads(myjson)
	except ValueError, e:
		return False
	return True

def send_mailgun(apikey, domainName, imagefile1, imagefile2, imagefile3, toEmail, ccEmail, txtSubject, txtContent):
	return requests.post(
		"https://api.mailgun.net/v3/"+domainName+"/messages",
		auth=("api", apikey),
		files=[("attachment", open(imagefile1))
			,("attachment", open(imagefile2))
			,("attachment", open(imagefile3))
			],
		data={"from": "HomeMonitor <monitor@"+domainName+">",
			"to": toEmail,
			"cc": ccEmail,
#			"bcc": "bar@example.com",
			"subject": txtSubject,
			"text": txtContent
#			"html": "<html>HTML version of the body</html>"
			})

def number2speakwords(numValue):
	strTMP = str(numValue)
	unitSpeak = ["", "十", "百", "千", "萬", "十", "百", "千"]

	if strTMP.find('.')==-1:
		strIntNum = strTMP
		strDecimal = ""
	else:
		NumSplit = strTMP.split('.')
		strIntNum = NumSplit[0]
		strDecimal = NumSplit[1]

	if len(strIntNum)>2 and strIntNum[len(strIntNum)-2]=="0": #十位是0
		if strIntNum[len(strIntNum)-1]!="0":
			nitSpeak[1] = '零'
		else:
			unitSpeak[1] = ''

	if len(strIntNum)>3 and strIntNum[len(strIntNum)-3]=="0": #百位是0
		unitSpeak[2] = ' '
	if len(strIntNum)>4 and strIntNum[len(strIntNum)-4]=="0": #千位是0
		unitSpeak[3] = ' '

	if len(strIntNum)>5:
		if strIntNum[len(strIntNum)-5]!="0": #萬位不是0
			unitSpeak[4] = "萬"
		else:
			unitSpeak[4] = ' '

		if len(strIntNum)>5 and strIntNum[len(strIntNum)-6]!="0": #萬位是0, 十萬位不是0
			unitSpeak[5] = "十萬"
		elif len(strIntNum)>6 and strIntNum[len(strIntNum)-7]!="0": #十萬位是0, 百萬位不是0
			unitSpeak[6] = "百萬"
		elif len(strIntNum)>7 and strIntNum[len(strIntNum)-8]!="0": #百萬位是0, 千萬位不是0
			unitSpeak[7] = "千萬"

	stringIntSpeak = ""
	for i in range(0, len(strIntNum)):
		stringIntSpeak = stringIntSpeak + strIntNum[i] + unitSpeak[len(strIntNum)-i-1]
		i=i+1

	stringIntSpeak = stringIntSpeak.replace("0", "")

	if len(strDecimal)>0:
		return stringIntSpeak + "點" + strDecimal
	else:
		return stringIntSpeak

def speakWords(wordsSpeak, speakerName, frequency, speed):
	nessContent = wordsSpeak
	newsArray = nessContent.split("｜")
	i=0
	person = speechClass.TTSspech()

	for newsSpeak in newsArray:
		logger.info("(" + str(len(newsSpeak)) + ") " + newsSpeak)
		person.setWords("\"" + newsSpeak + "\"")
		person.setSpeaker("\"" + speakerName + "\"")  # Bruce, Theresa, Angela, MCHEN_Bruce, MCHEN_Jo$
		person.setSpeed(speed)

		id = int(person.createConvertID())
		logger.info("URL: " + person.getVoiceURL())
		if(id>0):
			person.playVoice(frequency ,5)	

def lightLED(mode):
	if mode == 0:	#居家模式
		GPIO.output(pinLED_BLUE, GPIO.LOW)
		GPIO.output(pinLED_RED, GPIO.LOW)
		GPIO.output(pinLED_YELLOW, GPIO.HIGH)
	elif mode == 1:	# 外出模式
		GPIO.output(pinLED_BLUE, GPIO.HIGH)
		GPIO.output(pinLED_RED, GPIO.LOW)
		GPIO.output(pinLED_YELLOW, GPIO.LOW)
	else:
		GPIO.output(pinLED_BLUE, GPIO.LOW)
		GPIO.output(pinLED_RED, GPIO.HIGH)
		GPIO.output(pinLED_YELLOW, GPIO.HIGH)

def playWAV(wavFile):
	logger.info("PLAY WAV: "+wavFile)
	#call('omxplayer --no-osd ' + wavFile)
	call(["omxplayer","--no-osd",wavFile])
			
#--Cloudinary--------------------------
def dump_response(response):
	logger.info("Upload response:")
	for key in sorted(response.keys()):
		logger.info("  %s: %s" % (key, response[key]))

def upload_files(filename, width, height, tag, pid):
	logger.info("--- Upload a local file with custom public ID")
	response = upload(filename,
		tags = tag,
		public_id = pid,
	)
	dump_response(response)

	url, options = cloudinary_url(response['public_id'],
		format = response['format'],
		width = width,
		height = height,
		crop = "fit"
	)
	logger.info("Image uploaded to url: " + url)
	
#--Actions------------------------------
def read_Sentence1():  #靜心語
	wavNumber = str(random.randint(1, 80))
	playWAV("wav/sentence1/start.wav")
	playWAV("wav/sentence1/"+wavNumber+".wav")	


def read_Weather():

	dt = list(time.localtime())
	nowYear = dt[0]
	nowMonth = dt[1]
	nowDay = dt[2]
	nowHour = dt[3]
	nowMinute = dt[4]

	link = "http://data.sunplusit.com/Api/WeatherUVIF"
	f = urllib.urlopen(link)
	myfile = f.read()
	jsonData = json.loads(myfile)
	nowUV = "而目前室外紫外線指數是" + jsonData[0]['UVIStatus'] + ", " + jsonData[0]['ProtectiveMeasure']
	
	link = "http://data.sunplusit.com/Api/WeatherCWB"
	f = urllib.urlopen(link)
	myfile = f.read()
	jsonData = json.loads(myfile)
	nowWeather_tmp = "目前室外的氣象是" + jsonData[0]['Weather'] + ", " + jsonData[0]['Precipitation'] + ", " + jsonData[0]['Temperature'] + ", " +  jsonData[0]['RelativeHumidity'] + ", 整體來說氣候是" + jsonData[0]['ConfortIndex']
	nowWeather = nowWeather_tmp.replace("為", "是 ")

	link = "http://data.sunplusit.com/Api/WeatherAQX"
	f = urllib.urlopen(link)
	myfile = f.read()
	jsonData = json.loads(myfile)
	nowAir_tmp = "另外, 關於室外空氣指數部份, 目前室外的PM2.5數值為" + number2speakwords(jsonData[0]['PM25']) + ", PM十的數值為" + number2speakwords(jsonData[0]['PM10']) + ", 空氣品質PSI指數為" + number2speakwords(jsonData[0]['PSI']) + ", 整體來說空氣品質" + jsonData[0]['Status'] + ", " + jsonData[0]['HealthEffect'] + ", 建議" + jsonData[0]['ActivitiesRecommendation']
	nowAir_tmp = nowAir_tmp.replace(".", "點")
	nowAir = nowAir_tmp.replace("為", "是 ")
	
	speakString = "今天" + str(nowYear) + "年" + number2speakwords(int(nowMonth)) + "月" + number2speakwords(int(nowDay)) + "日  " + number2speakwords(int(nowHour)) + "點" + number2speakwords(int(nowMinute)) + "分  ," + nowWeather + " , " + nowUV + nowAir
	logger.info(speakString)

	speakWords(speakString, "MCHEN_Bruce", 48000, 0)

def alarmSensor(nowT, nowH, nowGAS, nowLight ):

	arrayWAVs = []
	
	if(nowGAS>100):
		arrayWAVs.append("wav/sensor/w2.wav") #危險，危險！空氣中偵測到媒氣外洩，請立即開門窗並檢查家中瓦斯！
		
	if(nowT<=16):
		#sensorAlarm+="現在室內氣溫為" + str(nowT) + "度，相當寒冷，建議您一定要多穿衣服保暖。"
		arrayWAVs.append("wav/sensor/w3.wav")  #現在室內氣溫為
		arrayWAVs.append("wav/number/" + str(nowT) + ".wav")
		arrayWAVs.append("wav/sensor/unitc.wav")   #度C
		arrayWAVs.append("wav/sensor/w4.wav")  #建議您一定要多穿衣服保暖。
	elif(nowT<=22 and nowT>16):
		#sensorAlarm+="現在室內氣溫為" + str(nowT) + "度，有些寒冷，建議您可以多穿件衣服保暖，以免感冒了。"
		arrayWAVs.append("wav/sensor/w3.wav")  #現在室內氣溫為
		arrayWAVs.append("wav/number/" + str(nowT) + ".wav")
		arrayWAVs.append("wav/sensor/unitc.wav")   #度C
		arrayWAVs.append("wav/sensor/w5.wav")  #有些寒冷，建議您可以多穿件衣服保暖，以免感冒了。
	elif(nowT<=30 and nowT>25):
		#sensorAlarm+="現在室內氣溫為" + str(nowT) + "度，氣溫剛剛好，相當舒適。"
		arrayWAVs.append("wav/sensor/w3.wav")  #現在室內氣溫為
		arrayWAVs.append("wav/number/" + str(nowT) + ".wav")
		arrayWAVs.append("wav/sensor/unitc.wav")   #度C
		arrayWAVs.append("wav/sensor/w6.wav")  #氣溫剛剛好，相當舒適。
	elif(nowT<=35 and nowT>30):
		#sensorAlarm+="現在室內氣溫為" + str(nowT) + "度，感覺有些悶熱，建議您可開啟空調冷氣來降低室溫。"
		arrayWAVs.append("wav/sensor/w3.wav")  #現在室內氣溫為
		arrayWAVs.append("wav/number/" + str(nowT) + ".wav")
		arrayWAVs.append("wav/sensor/unitc.wav")   #度C
		arrayWAVs.append("wav/sensor/w7.wav")  #感覺有些悶熱，建議您可開啟空調冷氣來降低室溫。
	elif(nowT<=40 and nowT>35):
		#sensorAlarm+="現在室內氣溫異常悶熱，已經" + str(nowT) + "度了，請立即檢查您的空調及冷氣系統。"
		arrayWAVs.append("wav/sensor/w8.wav")  #現在室內氣溫異常悶熱，已經有
		arrayWAVs.append("wav/number/" + str(nowT) + ".wav")
		arrayWAVs.append("wav/sensor/unitc.wav")   #度C
		arrayWAVs.append("wav/sensor/w9.wav")  #度了，請立即檢查您的空調及冷氣系統。
	elif(nowT>40):
		#sensorAlarm+="危險，危險！現在室內溫度高達" + str(nowT) + "度，已經超過常人可忍受的溫度警戒值，可能有火災發生，請注意安全。"
		arrayWAVs.append("wav/sensor/w10.wav")  #危險，危險！現在室內溫度高達
		arrayWAVs.append("wav/number/" + str(nowT) + ".wav")
		arrayWAVs.append("wav/sensor/unitc.wav")   #度C
		arrayWAVs.append("wav/sensor/w11.wav")	#已經超過常人可忍受的溫度警戒值，可能有火災發生，請檢查家中火源並注意安全。
	
	for sentence in arrayWAVs:
		playWAV(sentence)
	
	arrayWAVs = []
	
	if(nowH<=30):
		arrayWAVs.append("wav/sensor/w20.wav")  #溼度則是
		arrayWAVs.append("wav/number/" + str(nowH) + ".wav")
		arrayWAVs.append("wav/sensor/unitpercent.wav")   #%
		arrayWAVs.append("wav/sensor/w21.wav")  #空氣比較乾燥
	elif(nowH<=75 and nowH>30):
		arrayWAVs.append("wav/sensor/w20.wav")  #溼度則是
		arrayWAVs.append("wav/number/" + str(nowH) + ".wav")
		arrayWAVs.append("wav/sensor/unitpercent.wav")   #%
		arrayWAVs.append("wav/sensor/w22.wav")  #溼度正常相當舒服
	elif(nowH>75):
		arrayWAVs.append("wav/sensor/w20.wav")  #溼度則是
		arrayWAVs.append("wav/number/" + str(nowH) + ".wav")
		arrayWAVs.append("wav/sensor/unitpercent.wav")   #%
		arrayWAVs.append("wav/sensor/w23.wav")  #室內空氣很潮溼哦, 請考慮是否打開除潮機
		
	for sentence in arrayWAVs:
		playWAV(sentence)
		
def timeTell(hour, minute):
	arrayWAVs = []
	
	arrayWAVs.append("wav/clock/c1.wav")	#目前時刻
	arrayWAVs.append("wav/number/" + str(hour) + ".wav")
	arrayWAVs.append("wav/clock/hour.wav")   #點
	arrayWAVs.append("wav/number/" + str(minute) + ".wav")
	arrayWAVs.append("wav/clock/minute.wav")   #分

	for sentence in arrayWAVs:
		playWAV(sentence)

def EnvWarning(T, H, MQ4):
	global modeOperation, ENV_lastwarningtime, ENV_warning_repeat_period

	logger.info("Environment warning!")
	captureTime = time.localtime()

	if ((time.time()-ENV_lastwarningtime))>ENV_warning_repeat_period:
		picture_date = time.strftime("%H點%M分%S秒", captureTime)
		picture_filename1 = time.strftime("%Y%m%d%H%M%S", captureTime) + '1.jpg'
		camera.capture(picture_filename1)
		time.sleep(PIR_sleep_take_2_PicturesPeriod)
		upload_files(picture_filename1, 250, 250, "PIR_1", picture_filename1)

		picture_date = time.strftime("%H點%M分%S秒", captureTime)
		picture_filename2 = time.strftime("%Y%m%d%H%M%S", captureTime) + '2.jpg'
		camera.capture(picture_filename2)
		time.sleep(PIR_sleep_take_2_PicturesPeriod)
		upload_files(picture_filename2, 250, 250, "PIR_2", picture_filename2)

		picture_date = time.strftime("%H點%M分%S秒", captureTime)
		picture_filename3 = time.strftime("%Y%m%d%H%M%S", captureTime) + '3.jpg'
		camera.capture(picture_filename3)
		time.sleep(PIR_sleep_take_2_PicturesPeriod)
		upload_files(picture_filename3, 250, 250, "PIR_3", picture_filename3)
			
		txtSubject = "環境警報:"
		txtContent = ""
		if T>45:
			txtSubject += "溫度超過45度C "
			txtContent += "目前家中的溫度是" + T + "度C。"
		if MQ4>30:
			txtSubject += "煤氣可能外洩 "
			txtContent += "目前家中的煤氣指數是" + MQ4 + "。"
				
		send_mailgun(APIKEY_MAILGUN, API_MAILGUN_DOMAIN, picture_filename1, picture_filename2 , picture_filename3,  "myvno@hotmail.com", "ch.tseng@sunplusit.com", txtSubject, txtContent + ", 已立即拍攝相片，時間為" + picture_date + "。")
		ENV_lastwarningtime = time.time()

def playTV():
	tvfile = random.choice(tvList)
	playWAV(tvfile)
	
#for Interrupts--------------------------
def MOTION(pinPIR):
	global PIR_last_pictureTime, modeOperation, modeSecutiry_starttime, ENV_lastwarningtime, ENV_warning_repeat_period

	#print ("Security mode will start after " + str(modeSecutirt_waittime - (time.time()-modeSecutiry_starttime)))
	if modeOperation==1 and modeSecutiry_starttime>0 and ((time.time()-modeSecutiry_starttime)>modeSecutirt_waittime):
		logger.info("Motion Detected!")
		captureTime = time.localtime()

		if ((time.time()-PIR_last_pictureTime))>PIR_sleep_PictureAgainPeriod:

			picture_date = time.strftime("%H點%M分%S秒", captureTime)
			picture_filename1 = time.strftime("%Y%m%d%H%M%S", captureTime) + '1.jpg'
			camera.capture(picture_filename1)
			time.sleep(PIR_sleep_take_2_PicturesPeriod)
			upload_files(picture_filename1, 250, 250, "PIR_1", picture_filename1)

			picture_date = time.strftime("%H點%M分%S秒", captureTime)
			picture_filename2 = time.strftime("%Y%m%d%H%M%S", captureTime) + '2.jpg'
			camera.capture(picture_filename2)
			time.sleep(PIR_sleep_take_2_PicturesPeriod)
			upload_files(picture_filename2, 250, 250, "PIR_2", picture_filename2)

			picture_date = time.strftime("%H點%M分%S秒", captureTime)
			picture_filename3 = time.strftime("%Y%m%d%H%M%S", captureTime) + '3.jpg'
			camera.capture(picture_filename3)
			time.sleep(PIR_sleep_take_2_PicturesPeriod)
			upload_files(picture_filename3, 250, 250, "PIR_3", picture_filename3)
	
			send_mailgun(APIKEY_MAILGUN, API_MAILGUN_DOMAIN, picture_filename1, picture_filename2 , picture_filename3,  "myvno@hotmail.com", "ch.tseng@sunplusit.com", "PIR警報：有人入侵 " + picture_date, "PIR偵測到有人進入客廳, 已立即拍攝相片，時間為" + picture_date + "。")

			playWAV("wav/warning/warning1.wav")

			PIR_last_pictureTime = time.time()

	else:
		if modeOperation==1:
			if ((time.time()-ENV_lastwarningtime))>ENV_warning_repeat_period:
				tmpTime = (modeSecutirt_waittime - (time.time()-modeSecutiry_starttime))/60
				logger.info("In TIME: " + str(tmpTime) )

				if tmpTime<=1:
					playWAV("wav/startIn1min.wav")
				elif tmpTime<=3 and tmpTime>1:
					playWAV("wav/startIn3min.wav")
				elif tmpTime<=5 and tmpTime>3:
					playWAV("wav/startIn5min.wav")
				elif tmpTime<=10 and tmpTime>5:
					playWAV("wav/startIn10min.wav")
				elif tmpTime<=30 and tmpTime>10:
					playWAV("wav/startIn30min.wav")
				elif tmpTime>30:
					playWAV("wav/startAfter30min.wav")

				ENV_lastwarningtime = time.time()

def btn_Security(pinBTN_Security):
	global modeOperation, modeSecutiry_starttime, btn_secutiry_lastclicktime
	if (time.time()-btn_secutiry_lastclicktime)>5:		

		if modeOperation == 0:
			modeOperation = 1
			modeSecutiry_starttime = time.time()
			os.system('omxplayer --no-osd wav/mode1.wav')
		else:
			modeOperation = 0
			modeSecutiry_starttime = 0
			os.system('omxplayer --no-osd wav/mode0.wav')

		lightLED(modeOperation)
		logger.info('Button Pressed, mode change to ' + str(modeOperation))
		btn_secutiry_lastclicktime = time.time()
		
#Register----------------------------------------------
GPIO.add_event_detect(pinPIR, GPIO.RISING, callback=MOTION)
#GPIO.add_event_detect(pinBTN_Security, GPIO.FALLING, callback=btn_Security)

#Start--------------------------------------------------
lightLED(modeOperation)

try:
	while True:

		#print "PIR:" + str(GPIO.input(pinPIR))

		if GPIO.input(pinBTN_Security) == False:
			btn_Security(pinPIR)

		else:
			dt = list(time.localtime())
			nowYear = dt[0]
			nowMonth = dt[1]
			nowDay = dt[2]
			nowHour = dt[3]
			nowMinute = dt[4]

			#print("lastHourlySchedule=" + str(lastHourlySchedule) + " / nowHour=" + str(nowHour))

			if lastHourlySchedule==999:
				playWAV("wav/welcome/welcome1.wav") #您好，歡迎使用居家安全時鐘。按鈕 可切換居家或外出模式。
				lastHourlySchedule = nowHour
		
			#Environment information
			if (time.time()-ENV_lstchecktime)>ENV_checkPeriod:		
				statusPIR = GPIO.input(pinPIR)		
				adc = mcp3008.MCP3008()
				vLight = adc.read([mcp3008.CH1])
				vMQ4 = adc.read([mcp3008.CH2])
			
				logger.info("Time: " + str(nowYear) + '/' + str(nowMonth) + '/' + str(nowDay) + ' ' + str(nowHour) + ':' + str(nowMinute))
				logger.info("Mode: " + str(modeOperation))
				logger.info("PIR status: " + str(statusPIR))
				logger.info("Light #1: " + str(vLight[0])) # prints raw data [CH0]
				logger.info("MQ4: " + str(vMQ4[0])) # prints raw data [CH0]
				adc.close()

				h,t = dht.read_retry(dht.DHT22, pinDHT22)
				logger.info("Temperature:" + str(int(t)))
				logger.info("Humindity:" + str(int(h)))
				logger.info("-------------------------------------")

				ENV_lstchecktime = time.time()
			
			if modeOperation==0:
				#異常警示
				if t>40:
					EnvWarning(int(t), int(h),int(vMQ4[0]))
				else:		
					if nowHour>7 and nowHour<24:
						if lastHourlySchedule!=nowHour:
							lastHourlySchedule = nowHour

							#靜心語
							if nowHour==7 or nowHour==12 or nowHour==18 or nowHour==21:
								read_Sentence1()
										
							#整點報時					
							timeTell(nowHour, nowMinute)
							
							#室內溫度狀況告知					
							alarmSensor(int(t), int(h), int(vLight[0]), int(vMQ4[0]) )
							
							
							#室外氣象
							if nowHour==7 or nowHour==10 or nowHour==13 or nowHour==15:
								read_Weather()
							
							#if nowHour==7 or nowHour==12 or nowHour==18:
							#	playWAV("wav/news/n1.wav")	#下面為您播報重點新聞提要
							#	newsRead(NEWSREPORT_URL, NEWSREPORT_SPEAKER, 10)
						
						
			if modeOperation==1:
				#if GPIO.input(pinPIR) == True:
				#	MOTION(pinPIR)

				#else:
				#異常警示
				if t>40:
					EnvWarning(int(t), int(h),int(vMQ4[0]))

				#特定時間播放TV節目聲音
				if lastHourlySchedule!=nowHour:
					lastHourlySchedule = nowHour

				if nowHour==8 or nowHour==12 or nowHour==18:
					playTV()
					
		
except:
	print("Unexpected error:", sys.exc_info()[0])
	raise