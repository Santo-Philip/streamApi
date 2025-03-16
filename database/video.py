import uuid
from database.spbase import supabase
from typing import Optional, List, Dict, Any


def insert_video( msg, file_id, file_name):
    print(file_id)
    unique_id = str(uuid.uuid4())  # Generate a unique token

    data = {
        "user": msg.from_user.id,
        "video": file_id,
        "token": unique_id,
        "title": file_name
    }

    response = supabase.from_("stream").insert(data).execute()
    return response


def video_exists(file_id: str):
    response = supabase.table("stream").select("video").eq("video", file_id).limit(1).execute()
    if response.data:
        return response.data[0]["video"]
    return None


async def fetch_video(id: uuid.UUID) -> Optional[List[Dict[str, Any]]]:
    try:
        response = await supabase.table("stream").select("*") .eq("token", id).limit(1) .execute()

        if response.data and len(response.data) > 0:
            return response.data
        return None

    except Exception as e:
        print(f"Error fetching video with token {id}: {str(e)}")
        raise