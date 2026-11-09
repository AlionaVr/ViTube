import enum

from pydantic import BaseModel


class Rating(enum.StrEnum):
    LIKE = "like"
    DISLIKE = "dislike"
    NONE = "none"  # no rating: sending it takes a like or dislike back


class RatingIn(BaseModel):
    rating: Rating


class RatingOut(BaseModel):
    like_count: int
    my_rating: Rating
