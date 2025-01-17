from elevenlabs import generate, play

audio = generate(
    text="Testing voice generation",
    voice="Rachel"  # Using a default voice
)
play(audio)