# Podcasting Instruction (In progress)

## Show Notes
1. Create new folder named "Episode <xxx>" with leading zeroes
1. Make a copy of the episode template and move to the new folder
1. Rename document to the name of the folder
1. TODO

## Editing

### Setup
1. Create new audacity project
1. Drag all the audio files into audacity
    - **Select the option "Read the files directly from the original" during import**
1. Import the tracks twice (All effects are applied to one, the other is there in case we screw up)

### Sync Audio
1. Disable sync-lock (`Tracks->Sync-Lock Tracks (on/off)`)
1. If you have a combined skype recording, use that as the "time master" to slide the individual tracks to match it.
    - Mute all but two of the tracks and slide one around using the **Time Shift Tool(F5)** to line it up 
    - **Note that the remote recordings won't match exactly due to extra time delays from skype**
1. Once the tracks are sync-ed, re-enable sync-lock

### Edit all the things!
1. Select each track and run the Limiter effect with -3dB "Limit to" and 10ms Hold. This will get rid of the crazy peaks
1. Select a a few seconds of "silence" of each track to get a noise profile (Use Noise Reduction effect and select "Get Noise Profile") then select the entire track and run Noise Reduction again (I used the default settings 12 dB, 6 and 3)
1. Select each track and run the AGC effect. I normally use AGC strength 60 %. The squelch threshold will depend on how quiet/loud the track is. If the squelch is too high, some of the voice will get attenuated away. I usually have something around -25 dB and maximum attenuation of -30 dB (This way most of the quiet background noises get attenuated away.) 
1. At this point, I start listening to the entire episode. Whenever there's stuff that shouldn't be there, select and delete the section. If there's pops, clicks, and other unwanted noise, select the part you want to remove and press Ctrl+L to silence it.
1. If the AGC squelch threshold was too high, some speech might have gotten significantly attenuated. You can use the orignial, unmodified track to 'rescue' the audio. A simple copy paste + AGC again with lower squelch threshold for that particular area will do it.
1. Select all the tracks and re-run the limiter again with -3dB. The AGC might have amplified some parts a bit much.

### Add Intro/Outro
I usually put the cursor at time 0 and use Generate->Silence to get 30 seconds of silence at the beginning of the tracks. I then import the intro and outro wav files and place them accordingly. You'll need to disable sync-lock tracks again. 

### Exporting MP3
1. `File->Export->Export as Mp3`
1. Use the following settings:
    - **Filename:** episode_xx.mp3 (Where xx is episode number with no leading zero)
    - **Bit Rate Mode:** Constant
    - **Quality:** 96kpbs
    - **Channel Mode"** Force Export to mono
1. Metadata:
    - **Artist Name:** J. Costillo and A. Prieto
    - **Track Title:** xxx - Tile (Where xxx is three digit show number with leading zero AND spaces around " - ")
    - **Album Title:** Unnamed RE Show
    - **Track Number:** (Show number without leading zero)
    - **Year:** current year
    - **Genre:** podcast

### Audacity Project Archive
1. In Audacity, do `File->Export->Save Compressed Copy of Project`
1. Send to Alvaro for backup :D

## Publishing

### Show Notes
Make sure to add the shownotes to the google doc. These will be copy/pasted to the libsyn show description.

### Libsyn Upload
1. Got to `Content->Add New Episode`
1. In the **1. Media** tab, click on **Add Media File** and upload the mp3.
1. In the **2. Details** tab, add the title (same as the mp3 title).
    - Also add a subtitle like "interview with ____" or a few word (< 10) summary of the episode.
1. Paste in the shownotes from the google doc in the **Description** text box.
    - **DONT FORGET the comments/suggestions and music attribution bits.** They should already be on the google doc
1. Save as draft or publish as necessary
    - Do re-read the shownotes before publishing

## Github Site Update
### Update Directory ID
1. In libsyn, click on `Content->Previously Published`.
1. Click on the **Link/Embed** link for the episode
1. Copy the last number in the "Libsyn Directory URL"
1. Add it to directory_ids.csv with the episode number in front.

### Generate new page
1. Run `pipenv run ./rss.py`
1. cd into the github.io site
1. Commit the changes and push

## Twitter/etc
...
