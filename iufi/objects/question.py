import Levenshtein

from difflib import SequenceMatcher

QUIZ_LEVEL_BASE: dict[str, tuple[int, tuple[int, int, hex]]] = {
    "easy": (10, (1, 1, 0x7CD74B)),
    "medium": (20, (3, 2, 0xF9E853)),
    "hard": (30, (5, 3, 0xD75C4B))
}

class Question:
    def __init__(
        self,
        _id: int,
        question: str,
        answers: list[str],
        num_correct: int = 0,
        num_wrong: int = 0,
        average_time: float = 0.0,
        attachment: str = None,
        records: dict | None = None,
        tips: str = "",
        default_level: str = None
    ):
        self.id = _id
        self.question: str = question
        self.answers: list[str] = answers
        self.attachment: str | None = attachment
        self.tips: str = tips

        self._correct: int = num_correct
        self._wrong: int = num_wrong
        self._average_time: float = average_time
        self._default_level: str = default_level
        self._records: dict | None = records if records else {}

        self.is_updated: bool = False

    def check_answer(self, answer: str, threshold: float = .75) -> bool:
        answer = answer.lower()
        is_number_or_date = self.is_number_or_date(answer)
        for model_answer in self.answers:

            model_answer = model_answer.lower()

            if is_number_or_date:
                if model_answer == answer:
                    return True
                continue

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

    def is_number_or_date(self, answer: str) -> bool:
        return answer.replace(" ", "").replace("/", "").replace(".", "").replace("-", "").isdigit()

    def update_average_time(self, time: float) -> None:
        if not self.is_updated:
            self.is_updated = True

        self._average_time = ((self._average_time * self.total) + time) / (self.total + 1) if self.total > 0 else time

    def update_user(self, user_id: int, answer: str, response_time: float, is_correct: bool = None) -> None:
        if not self.is_updated:
            self.is_updated = True

        user_id = str(user_id)
        if user_id not in self._records:
            self._records[user_id] = {
                "answers": []
            }

        user_record = self._records[user_id]
        if answer not in user_record["answers"]:
            user_record["answers"].append(answer)

        if is_correct:
            user_record["fastest_response_time"] = min(user_record.get("fastest_response_time", float("inf")), round(response_time, 1))

    def best_record(self) -> tuple[str, float] | None:
        sorted_records = sorted((item for item in self._records.items() if item[1].get("fastest_response_time")), key=lambda item: item[1]["fastest_response_time"])

        # Return the user ID and fastest_response_time of the first record
        return (sorted_records[0][0], sorted_records[0][1]["fastest_response_time"]) if sorted_records else None
    
    def toDict(self) -> dict:
        if self.is_updated:
            self.is_updated = False

        return {
            "question": self.question,
            "answers": self.answers,
            "num_correct": self._correct,
            "num_wrong": self._wrong,
            "average_time": self.average_time,
            "attachment": self.attachment,
            "records": self._records,
            "default_level": self._default_level
        }
    
    @property
    def level(self) -> str:
        if self._default_level:
            return self._default_level
        
        if self.correct_rate >= 85 or self._wrong == 0:
            return "easy"
        elif self.correct_rate >= 40:
            return "medium"
        else:
            return "hard"

    @property
    def average_time(self) -> float:
        base_time = QUIZ_LEVEL_BASE.get(self.level)[0]

        if not self._average_time:
            return base_time
        
        return round((self._average_time + base_time) / 2, 1)

    @property
    def total(self) -> int:
        return self._correct + self._wrong
    
    @property
    def correct_rate(self) -> float:
        total = self.total
        if not total:
            return 0
        return round(self._correct / total, 2) * 100
    
    @property
    def wrong_rate(self) -> float:
        if self._wrong == 0:
            return 0
        
        return 100 - self.correct_rate