
import os
import yt_dlp
import asyncio
import Levenshtein

from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional
from discord import FFmpegPCMAudio, Member

from .config import Config

class Track():
    def __init__(
        self,
        data: Dict[str, Any]
    ):  
        self.data: Dict[str, Any] = data
        self.is_updated: bool = False
        self.ytdl = yt_dlp.YoutubeDL({
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(Config.get().MUSIC_TRACKS_FOLDER_PATH, '%(id)s.%(ext)s'),
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
        })

    async def load_data(self, *, stream=False) -> Dict[str, Any]:
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: YTDL.extract_info(self.url, download=not stream))
            
            self.data["yt_data"] = {
                "title": data.get("title", "--"),
                "duration": data.get("duration", 0),
                "album": data.get("album", "--"),
                "artists": data.get("artists", []),
                "release_year": data.get("release_year", "----")
            }
            self.is_updated = True
        
        except Exception as e:
            func.logger.info("An exception occurred while loading track info from YouTube.", exc_info=e)
    
    async def get_audio_file_path(self) -> Optional[str]:
        for item in os.listdir(Config.get().MUSIC_TRACKS_FOLDER_PATH):
            if os.path.splitext(item)[0] == self.id:
                return os.path.join(Config.get().MUSIC_TRACKS_FOLDER_PATH, item)
        
        await self.load_data()
        return self.get_audio_file_path(self)

    def check_answer(self, answer: str, threshold: float = .9) -> bool:
        answer = answer.lower()

        for model_answer in self.answers:
            model_answer = model_answer.lower()

            string1 = set(model_answer.split())
            string2 = set(answer.split())
            jac_similarity = len(string1 & string2) / len(string1 | string2)

            string1 = model_answer.replace(" ", "")
            string2 = answer.replace(" ", "")
            lev_similarity = Levenshtein.ratio(string1, string2)
            seq_similarity = SequenceMatcher(None, string1, string2).ratio()

            if lev_similarity >= threshold or jac_similarity >= threshold or seq_similarity >= threshold:
                return True
        return False

    def update_state(self, member: Member, time_used: float, result: bool) -> None:
        self.is_updated = True

        self.data["average_time"] = ((self.data["average_time"] * self.total) + time_used) / (self.total + 1) if self.total > 0 else time_used

        current_best_time = self.data["best_record"]["time"]
        if result and (not current_best_time or current_best_time > time_used):
            self.data["best_record"]["member"] = member.id
            self.data["best_record"]["time"] = time_used

        key = "correct" if result else "wrong"
        self.data[key] = self.data.get(key, 0) + 1

    async def source(self, start: float = 0) -> FFmpegPCMAudio:
        return FFmpegPCMAudio(await Track.get_audio_file_path(self), options=f'-vn -ss {start}')
    
    @property
    def is_loaded(self) -> bool:
        return "yt_data" in self.data
    
    @property
    def id(self) -> str:
        return self.data.get("_id")

    @property
    def url(self) -> str:
        return self.data.get("url")
    
    @property
    def thumbnail(self) -> str:
        return f"https://i.ytimg.com/vi/{self.id}/maxresdefault.jpg"
    
    @property
    def title(self) -> str:
        return self.data["yt_data"]["title"]

    @property
    def duration(self) -> int:
        return self.data["yt_data"]["duration"]
    
    @property
    def album(self) -> str:
        return self.data["yt_data"]["album"]
    
    @property
    def artists(self) -> List[str]:
        return self.data["yt_data"]["artists"]
    
    @property
    def release_year(self) -> str:
        return self.data["yt_data"]["release_year"]
    
    @property
    def total(self) -> int:
        return self.data["correct"] + self.data["wrong"]
    
    @property
    def average_time(self) -> float:
        return self.data["average_time"]
    
    @property
    def correct_rate(self) -> float:
        total = self.total
        if not total:
            return 0
        return round(self.data["correct"] / total, 2) * 100
    
    @property
    def wrong_rate(self) -> float:
        return 100 - self.correct_rate

    @property
    def best_record(self) -> tuple[int, float]:
        br = self.data["best_record"]
        return br["member"], br["time"]

    @property
    def answers(self) -> List[str]:
        return self.data["answers"]

    @property
    def likes(self) -> int:
        return self.data["likes"]