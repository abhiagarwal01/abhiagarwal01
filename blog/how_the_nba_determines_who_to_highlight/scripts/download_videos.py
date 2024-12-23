from concurrent.futures import ThreadPoolExecutor, as_completed
import pickle
from typing import Any
from pytubefix import YouTube, Playlist
from pytubefix.exceptions import PytubeFixError
import shelve
from pathlib import Path
from rich.progress import Progress

working_dir = Path(__file__).parent / "data"

highlight_playlists = {
    "2020": "https://www.youtube.com/playlist?list=PLlVlyGVtvuVlr5GAksVQA37IE83MzRqln",
    "2021": "https://www.youtube.com/playlist?list=PLlVlyGVtvuVkIjURb-twQc1lsE4rT1wfJ",
    "2022": "https://www.youtube.com/playlist?list=PLlVlyGVtvuVm4_E_faSFuu3nU0F9O6XbR",
    "2023": "https://www.youtube.com/playlist?list=PLlVlyGVtvuVkAiuNG6gXxaUgjekofxxgs",
    "2024": "https://www.youtube.com/playlist?list=PLlVlyGVtvuVkxr3RnRwVqtuWR7BSBE0tD",
}


def po_token_verifier() -> tuple[str, str]:
    PO_TOKEN = "MnQuZmvGMxz-LC5e5e1D06JcspAJg8vXa1nGhNd287tQDuEJp3GC1OX8A79vvjB7DeOhO2iJidzJB1WKD9KF8LR1qWDRLGhEV-Ms-9PsN3XJKJWtzgTOwGM8joYXQ4QBxKDywXvjisECsztSJoi7gGLMyEPsJw=="
    VISITOR_DATA = "Cgt1ZnQ2eDE0NWRqZyjz9aK6BjIKCgJVUxIEGgAgXg%3D%3D"
    return (VISITOR_DATA, PO_TOKEN)


all_videos_pickle = working_dir / "all_videos.pkl"
if all_videos_pickle.exists():
    all_videos: list[YouTube] = pickle.loads(all_videos_pickle.read_bytes())
else:
    print("Downloading videos in playlist...")
    all_videos = []
    for playlist_url in highlight_playlists.values():
        videos = [
            video
            for video in Playlist(
                playlist_url, use_po_token=True, po_token_verifier=po_token_verifier
            ).videos
        ]
        all_videos.extend(videos)
    all_videos_pickle.write_bytes(pickle.dumps(all_videos))
    print("Downloaded videos")
print(f"Video count = {len(all_videos)}")


def get_video_details(video: YouTube) -> tuple[Any, ...]:
    return (video.title, video.views, video.thumbnail_url, video.publish_date)


def add_details(db: shelve.Shelf, videos: list[YouTube]) -> None:
    with ThreadPoolExecutor() as executor, Progress() as progress:
        task = progress.add_task("videos", total=len(videos))
        future_to_video = {}
        for video in videos:
            vid_id = video.video_id
            if vid_id in db:
                #progress.console.print(f"Skipping {vid_id}")
                progress.advance(task, 1)
                continue
            future = executor.submit(get_video_details, video)
            future_to_video[future] = vid_id

        for future in as_completed(future_to_video):
            vid_id = future_to_video[future]
            try:
                details = future.result()
                progress.console.print(f"Adding {vid_id}")
                db[vid_id] = details
            except PytubeFixError as e:
                print(f"Error processing video {vid_id}: {e}")
                continue
            except Exception as e:
                print(f"Unexpected error with video {vid_id}: {e}")
                continue
            finally:
                progress.advance(task, 1)


print("Opening shelf with data")
with shelve.open(working_dir / "vid_details") as db:
    add_details(db, all_videos)
