import requests
from tqdm import tqdm


def download(
    url: str, 
    filename: str, 
    auth: tuple = None, 
    chunk_size: int = 1024,
    update_threshold = 1024*1024*128
) -> None:
    with open(filename, 'wb') as f:
        with requests.get(url, stream=True, auth=auth) as r:
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))

            tqdm_params = {
                'desc': url,
                'total': total,
                'miniters': 1,
                'unit': 'B',
                'unit_scale': True,
                'unit_divisor': 1024,
            }
            total_downloaded = 0
            last_update = 0  # Keep track of the last update

            with tqdm(**tqdm_params) as pb:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    total_downloaded += len(chunk)
                    
                    # Check if 1 GB threshold is reached since the last update
                    if total_downloaded - last_update >= update_threshold:
                        pb.update(total_downloaded - last_update)  # Update progress bar
                        last_update = total_downloaded
            
            # Compare the resulting length
            if total and total_downloaded != total:
                raise ValueError(f"Downloaded file size mismatch: expected {total} bytes, got {total_downloaded} bytes")
            elif total == 0:
                print("Warning: Content-Length header not provided, cannot verify the file size.")