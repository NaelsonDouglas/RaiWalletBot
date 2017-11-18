#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# RaiBlocks Telegram bot
# @RaiWalletBot https://t.me/RaiWalletBot
# 
# Source code:
# https://github.com/SergiySW/RaiWalletBot
# 
# Released under the BSD 3-Clause License
# 
# 
# Run by cron every minute
# 

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import Bot, ParseMode
import logging
import urllib3, certifi, socket, json
import time, math

# Parse config
import ConfigParser
config = ConfigParser.ConfigParser()
config.read('bot.cfg')
api_key = config.get('main', 'api_key')
bitgrail_price = config.get('monitoring', 'bitgrail_price')

header = {'user-agent': 'RaiWalletBot/1.0'}

# MySQL requests
from common_mysql import *



# Common functions
from common import push, mrai_text


# Translation
with open('language.json') as lang_file:
	language = json.load(lang_file)

def lang_text(text_id, lang_id):
	try:
		return language[lang_id][text_id]
	except KeyError:
		return language['en'][text_id]


def mercatox():
	http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED',ca_certs=certifi.where())
	url = 'https://mercatox.com/public/json24'
	#response = http.request('GET', url, headers=header, timeout=20.0)
	response = http.request('GET', url, timeout=20.0)
	json_mercatox = json.loads(response.data)
	json_array = json_mercatox['pairs']['XRB_BTC']
	try:
		last_price = int(float(json_array['last']) * (10 ** 8))
	except KeyError:
		last_price = 0
	high_price = int(float(json_array['high24hr']) * (10 ** 8))
	low_price = int(float(json_array['low24hr']) * (10 ** 8))
	ask_price = int(float(json_array['lowestAsk']) * (10 ** 8))
	bid_price = int(float(json_array['highestBid']) * (10 ** 8))
	volume = int(float(json_array['baseVolume']))
	btc_volume = int(float(json_array['quoteVolume']) * (10 ** 8))
	
	mysql_set_price(1, last_price, high_price, low_price, ask_price, bid_price, volume, btc_volume)


def bitgrail():
	http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED',ca_certs=certifi.where())
	#response = http.request('GET', bitgrail_price, headers=header, timeout=20.0)
	response = http.request('GET', bitgrail_price, timeout=20.0)
	json_bitgrail = json.loads(response.data)
	json_array = json_bitgrail['response']
	last_price = int(float(json_array['last']) * (10 ** 8))
	high_price = int(float(json_array['high']) * (10 ** 8))
	low_price = int(float(json_array['low']) * (10 ** 8))
	ask_price = int(float(json_array['ask']) * (10 ** 8))
	bid_price = int(float(json_array['bid']) * (10 ** 8))
	volume = int(float(json_array['coinVolume']))
	btc_volume = int(float(json_array['volume']) * (10 ** 8))
	
	mysql_set_price(2, last_price, high_price, low_price, ask_price, bid_price, volume, btc_volume)


def bitflip():
	http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED',ca_certs=certifi.where())
	url = 'https://api.bitflip.cc/method/market.getOHLC'
	json_data = json.dumps({"version": "1.0", "pair": "XRB:BTC"})
	response = http.request('POST', url, body=json_data, headers={'Content-Type': 'application/json'}, timeout=20.0)
	json_bitfilp = json.loads(response.data)
	json_array = json_bitfilp[1]
	last_price = int(float(json_array['close']) * (10 ** 8))
	high_price = int(float(json_array['high']) * (10 ** 8))
	low_price = int(float(json_array['low']) * (10 ** 8))
	volume = int(float(json_array['volume']))
	btc_volume = 0
	if (last_price == 0):
		price = mysql_select_price()
		last_price = int(price[2][0])
	
	url = 'https://api.bitflip.cc/method/market.getRates'
	json_data = json.dumps({"version": "1.0", "pair": "XRB:BTC"})
	response = http.request('POST', url, body=json_data, headers={'Content-Type': 'application/json'}, timeout=20.0)
	json_bitfilp = json.loads(response.data)
	json_array = json_bitfilp[1]
	for pair in json_array:
		if (pair['pair'] in 'XRB:BTC'):
			ask_price = int(float(pair['sell']) * (10 ** 8))
			bid_price = int(float(pair['buy']) * (10 ** 8))
	
	mysql_set_price(3, last_price, high_price, low_price, ask_price, bid_price, volume, btc_volume)


def prices_above_below(bot, user_id, price, exchange, above):
	lang_id = mysql_select_language(user_id)
	btc_price = ('%.8f' % (float(price) / (10 ** 8)))
	if (above == 1):
		text = lang_text('prices_above', lang_id).format(exchange, btc_price)
	else:
		text = lang_text('prices_below', lang_id).format(exchange, btc_price)
	try:
		push(bot, user_id, text)
	except Exception as e:
		print('Exception user_id {0}'.format(user_id))
	print(text)
	if (above == 1):
		mysql_delete_price_high(user_id)
	else:
		mysql_delete_price_low(user_id)
	time.sleep(0.5)


def price_check():
	bot = Bot(api_key)
	price = mysql_select_price()
	
	# check if higher
	users_high = mysql_select_price_high()
	price_high_bitgrail = max(int(price[1][0]), int(price[1][4]))
	price_high_mercatox = max(int(price[0][0]), int(price[0][4]))
	#price_high_bitflip = max(int(price[2][0]), int(price[2][4]))
	for user in users_high:
		if ((price_high_bitgrail >= int(user[1])) and ((int(user[2]) == 0) or (int(user[2]) == 1))):
			prices_above_below(bot, user[0], price_high_bitgrail, "BitGrail.com", 1)
		elif ((price_high_mercatox >= int(user[1])) and ((int(user[2]) == 0) or (int(user[2]) == 2))):
			prices_above_below(bot, user[0], price_high_mercatox, "Mercatox.com", 1)
		#elif ((price_high_bitflip >= int(user[1])) and ((int(user[2]) == 0) or (int(user[2]) == 3))):
		#	prices_above_below(bot, user[0], price_high_bitflip, "BitFlip.cc", 1)
	
	# check if lower
	users_low = mysql_select_price_low()
	price_low_bitgrail = min(int(price[1][0]), int(price[1][3]))
	price_low_mercatox = min(int(price[0][0]), int(price[0][3]))
	#price_low_bitflip = min(int(price[2][0]), int(price[2][3]))
	for user in users_low:
		if ((price_low_bitgrail <= int(user[1])) and ((int(user[2]) == 0) or (int(user[2]) == 1))):
			prices_above_below(bot, user[0], price_low_bitgrail, "BitGrail.com", 0)
		elif ((price_low_mercatox <= int(user[1])) and ((int(user[2]) == 0) or (int(user[2]) == 2))):
			prices_above_below(bot, user[0], price_low_mercatox, "Mercatox.com", 0)
		#elif ((price_low_bitflip <= int(user[1])) and ((int(user[2]) == 0) or (int(user[2]) == 3))):
		#	prices_above_below(bot, user[0], price_low_bitflip, "BitFlip.cc", 0)

def prices_usual():
	try:
		mercatox()
	except:
		time.sleep(1) # too many errors from Mercatox API
	try:
		bitgrail()
	except:
		time.sleep(5)
		try:
			bitgrail()
		except:
			time.sleep(1) # even BitGrail can fail
	try:
		bitflip()
	except:
		time.sleep(5)
		try:
			bitflip()
		except:
			time.sleep(1)
	
	price_check()


time.sleep(15)
prices_usual()
