from pathlib import Path
import aiohttp
import aiohttp.client_exceptions
import polars as pl
from aiohttp import ClientSession
from asyncio import Semaphore, TaskGroup
import uvloop

LIMITER = Semaphore(32)

working_dir = Path(__file__).parent.parent
data_dir = working_dir / "data"
headshot_dir = working_dir / "assets" / "headshots"

URL_TEMPLATE = (
    "https://cdn.nba.com/headshots/nba/{team_id}/{year}/1040x760/{player_id}.png"
)


async def download_file(
    session: ClientSession, player_id: int, season: str, team_id: int
) -> None:
    file_path = headshot_dir / season / str(team_id) / f"{player_id}.png"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    url = URL_TEMPLATE.format(team_id=team_id, year=season[:4], player_id=player_id)
    try:
        async with session.get(url) as resp, LIMITER:
            with file_path.open("wb") as f:
                async for data in resp.content.iter_chunked(1024):
                    f.write(data)
    except aiohttp.client_exceptions.ClientResponseError as e:
        if e.status == 403:
            return
        else:
            print(f"Error downloading {url}")


async def main() -> None:
    box_score_df = pl.read_parquet(data_dir / "box_scores.parquet")
    count_df = box_score_df.group_by("player_id", "season_year", "team_id").agg(
        pl.count().alias("count")
    )
    async with (
        ClientSession(
            # base_url="https://i.ytimg.com"
            raise_for_status=True,
        ) as session,
        TaskGroup() as tg,
    ):
        for row in count_df.iter_rows():
            player_id, season, team_id, _ = row
            tg.create_task(download_file(session, player_id, season, team_id))


uvloop.run(main())
