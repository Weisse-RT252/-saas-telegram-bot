import os
import asyncio
import httpx
import logging
from stem import Signal
from stem.control import Controller
from stem.util import term

class TorManager:
    def __init__(self):
        self.control_port = 9051
        self.password = os.getenv("TOR_PASSWORD")
        self.current_ip = None
        self.http_client = httpx.AsyncClient(
            proxies="socks5://127.0.0.1:9050",
            timeout=30.0
        )
        
    async def initialize(self):
        """Инициализация соединения с Tor"""
        self.current_ip = await self.get_current_ip()
        logging.info(f"Инициализирован Tor с IP: {self.current_ip}")
        return self
        
    async def renew_identity(self):
        """Смена Tor цепи с проверкой IP"""
        old_ip = self.current_ip
        try:
            with Controller.from_port(port=self.control_port) as controller:
                controller.authenticate(password=self.password)
                controller.signal(Signal.NEWNYM)
                
                # Ожидание применения изменений
                await asyncio.sleep(25)
                
                new_ip = await self.get_current_ip()
                if new_ip == old_ip:
                    raise ConnectionError("IP не изменился после обновления цепи")
                    
                self.current_ip = new_ip
                logging.info(term.format(f"IP изменен {old_ip} → {new_ip}", term.Color.GREEN))
                return True
                
        except Exception as e:
            logging.error(term.format(f"Ошибка ротации IP: {str(e)}", term.Color.RED))
            return False
            
    async def get_current_ip(self):
        """Получение текущего внешнего IP через Tor"""
        try:
            response = await self.http_client.get("https://api.ipify.org")
            return response.text
        except Exception as e:
            logging.error(f"Ошибка получения IP: {str(e)}")
            return "Не удалось определить IP"
            
    async def verify_connection(self, test_url="https://google.com"):
        """Проверка работоспособности соединения"""
        try:
            response = await self.http_client.get(test_url, timeout=15)
            return response.status_code == 200
        except Exception:
            return False
            
    async def rotate_until_success(self, max_attempts=5):
        """Циклическая смена IP до успешного соединения"""
        for attempt in range(max_attempts):
            logging.info(f"Попытка {attempt+1}/{max_attempts} смены IP...")
            if await self.renew_identity() and await self.verify_connection():
                return True
            await asyncio.sleep(10 * (attempt + 1))
        raise ConnectionError("Не удалось установить рабочее соединение через Tor")

# Глобальный экземпляр для удобства использования
tor_manager = TorManager() 