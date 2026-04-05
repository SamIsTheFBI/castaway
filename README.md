<div align="center">
  <pre>‧₊˚♪ 𝄞₊˚⊹ ࣪ ˖     𝐜𝐚𝐬𝐭𝐚𝐰𝐚𝐲     .✦ ݁˖ ‧₊˚♪ 𝄞₊˚⊹</pre>
  <i>A way to create radio station for your local network & listen across devices.</i>
</div>

## requirements
- python >= 3.12
- aiohttp
- ffmpeg

## setup

- Install dependencies:
  ```sh
  uv venv && source .venv && uv sync

  # use your os/distro's package manager to install ffmpeg
  sudo pacman -Sy ffmpeg
  ```
- Config:
  ```sh
  vi main.py # edit MUSIC_DIR
  ```
- Run the program:
  ```sh
  python main.py
  ```
## why

i have been slowly converting my arch linux setup to something of a home server & thought it'd be cool to have a music service running on it. wait, i already use mpd+ncmpcpp lets use it as a cool 24/7 radio! little did i know even though you can expose it to lan but audio output can be very different for different devices (my work macbook doesn't use pipewire ofc) and i couldn't find any answers that worked for me. 

hence this little script to use python+ffmpeg to create an audio stream over http that any client can use.
