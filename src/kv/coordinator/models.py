from pydantic import BaseModel, ConfigDict, Field, model_validator

TABLE_NAME_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


class TableDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=TABLE_NAME_PATTERN)
    partition_key: str = Field(min_length=1)
    sort_key: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def keys_differ(self):
        if self.sort_key == self.partition_key:
            raise ValueError("sort_key must differ from partition_key")
        return self
