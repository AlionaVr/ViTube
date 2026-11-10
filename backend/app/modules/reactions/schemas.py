import enum

from pydantic import BaseModel

from app.modules.reactions.models import DISLIKE, LIKE


class Rating(enum.StrEnum):
    LIKE = "like"
    DISLIKE = "dislike"
    NONE = "none"  # no rating: sending it takes a like or dislike back

    @property
    def stored(self) -> int | None:
        """The value in a reaction table; None: no row."""
        return {Rating.LIKE: LIKE, Rating.DISLIKE: DISLIKE}.get(self)

    @classmethod
    def of(cls, stored: int | None) -> "Rating":
        if stored is None:
            return cls.NONE
        return cls.LIKE if stored == LIKE else cls.DISLIKE


class RatingIn(BaseModel):
    rating: Rating


class RatingOut(BaseModel):
    like_count: int
    my_rating: Rating
