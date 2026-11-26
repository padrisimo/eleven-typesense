#!/usr/bin/env python3
"""Load 200,000 reproducible sounds into Postgres using COPY."""

import argparse
import os
import random
from datetime import datetime, timedelta, timezone

import psycopg

random.seed(42)

CATEGORIES = [
    "Explosions", "Footsteps", "Doors", "Ambience", "Weapons",
    "Sci-Fi", "Foley", "Vehicles", "Nature", "UI",
]
CATEGORY_WEIGHTS = [20, 15, 12, 15, 10, 8, 8, 7, 3, 2]

VOCAB = {
    "Explosions": {
        "adjectives": ["massive", "small", "distant", "close", "muffled", "sharp", "rolling", "concussive"],
        "nouns": ["explosion", "blast", "detonation", "bang", "boom", "burst", "eruption", "impact"],
        "modifiers": ["indoor", "outdoor", "underwater", "in tunnel", "with debris", "clean", "echoing"],
        "tags": ["explosion", "blast", "action", "destruction", "loud", "impact"],
    },
    "Footsteps": {
        "adjectives": ["heavy", "light", "fast", "slow", "running", "walking", "sneaking", "limping"],
        "nouns": ["footsteps", "steps", "footfalls", "treads", "paces"],
        "modifiers": ["on wood", "on concrete", "on gravel", "on metal", "on grass", "on carpet", "stairs", "creaking"],
        "tags": ["footsteps", "foley", "movement", "walking", "human"],
    },
    "Doors": {
        "adjectives": ["heavy", "light", "creaking", "slamming", "slow", "fast", "rusty", "smooth"],
        "nouns": ["door", "gate", "hatch", "portal", "entrance"],
        "modifiers": ["opening", "closing", "locking", "unlocking", "knocking", "sliding", "revolving"],
        "tags": ["door", "foley", "mechanical", "interior", "entrance"],
    },
    "Ambience": {
        "adjectives": ["quiet", "loud", "peaceful", "tense", "eerie", "busy", "calm", "stormy"],
        "nouns": ["ambience", "atmosphere", "room tone", "background", "soundscape", "environment"],
        "modifiers": ["forest", "city", "rain", "wind", "crowd", "factory", "office", "cave", "space", "underwater"],
        "tags": ["ambience", "background", "atmosphere", "loop", "environment"],
    },
    "Weapons": {
        "adjectives": ["rifle", "pistol", "shotgun", "machine gun", "sniper", "laser", "plasma", "silenced"],
        "nouns": ["shot", "fire", "discharge", "burst", "round", "volley"],
        "modifiers": ["single", "automatic", "reloading", "cocking", "dry fire", "with echo", "indoor", "outdoor"],
        "tags": ["weapon", "gun", "action", "combat", "shooting", "military"],
    },
    "Sci-Fi": {
        "adjectives": ["futuristic", "alien", "robotic", "energy", "digital", "holographic", "cybernetic", "warp"],
        "nouns": ["beam", "pulse", "hum", "whir", "scan", "teleport", "force field", "engine", "alert"],
        "modifiers": ["startup", "shutdown", "charging", "firing", "idle", "malfunction", "powering up"],
        "tags": ["sci-fi", "futuristic", "technology", "space", "digital", "ui"],
    },
    "Foley": {
        "adjectives": ["crisp", "muffled", "wet", "dry", "rough", "smooth", "hard", "soft"],
        "nouns": ["cloth", "paper", "glass", "metal", "wood", "plastic", "liquid", "impact", "scratch", "rub"],
        "modifiers": ["handling", "movement", "break", "tear", "crumple", "pour", "splash", "drip"],
        "tags": ["foley", "detail", "close-mic", "texture", "material"],
    },
    "Vehicles": {
        "adjectives": ["car", "truck", "motorcycle", "engine", "electric", "diesel", "vintage", "modern"],
        "nouns": ["engine", "start", "idle", "rev", "acceleration", "deceleration", "pass by", "horn", "brake"],
        "modifiers": ["fast", "slow", "distant", "close", "interior", "exterior", "tunnel", "highway"],
        "tags": ["vehicle", "transport", "engine", "movement", "travel"],
    },
    "Nature": {
        "adjectives": ["gentle", "violent", "calm", "stormy", "tropical", "arctic", "morning", "night"],
        "nouns": ["rain", "wind", "thunder", "waves", "birds", "insects", "waterfall", "stream", "fire", "earthquake"],
        "modifiers": ["light", "heavy", "distant", "close", "forest", "ocean", "mountain", "desert"],
        "tags": ["nature", "weather", "outdoor", "environment", "organic"],
    },
    "UI": {
        "adjectives": ["click", "pop", "chime", "beep", "whoosh", "ding", "buzz", "notification"],
        "nouns": ["button", "alert", "success", "error", "warning", "menu", "transition", "toggle", "slider"],
        "modifiers": ["soft", "sharp", "melodic", "digital", "mechanical", "subtle", "loud", "confirm", "cancel"],
        "tags": ["ui", "interface", "notification", "feedback", "app", "game"],
    },
}

FORMATS = ["wav", "mp3", "flac"]
SAMPLE_RATES = [44100, 48000, 96000]
LICENSES = ["library-standard", "library-extended", "cc0", "royalty-free"]
EXTRA_TAGS = ["stereo", "mono", "loop", "one-shot", "high-fidelity", "field-recording", "studio"]
START = datetime(2023, 1, 1, tzinfo=timezone.utc)
DAY_RANGE = 730


def make_row(index: int):
    category = random.choices(CATEGORIES, weights=CATEGORY_WEIGHTS, k=1)[0]
    v = VOCAB[category]
    title = f"{random.choice(v['adjectives'])} {random.choice(v['nouns'])} {random.choice(v['modifiers'])}".title()
    description = random.choice([
        f"A {title.lower()} sound effect, perfect for {random.choice(v['modifiers'])}.",
        f"High-quality {title.lower()} recording captured in {random.choice(v['modifiers'])}.",
        f"Professional {title.lower()} with {random.choice(v['adjectives'])} character.",
        f"{title} - {random.choice(v['adjectives']).capitalize()} {random.choice(v['nouns'])} {random.choice(v['modifiers'])}.",
    ])
    tags = random.sample(v["tags"], k=min(3, len(v["tags"]))) + random.sample(EXTRA_TAGS, k=random.randint(0, 3))
    if category in ("Ambience", "Nature"):
        duration_ms = random.randint(5000, 60000)
    elif category in ("UI", "Foley"):
        duration_ms = random.randint(100, 3000)
    else:
        duration_ms = random.randint(500, 10000)
    bpm = random.choice([60, 70, 80, 90, 100, 110, 120, 128, 140]) if category == "Ambience" and random.random() < 0.1 else None
    fmt = random.choice(FORMATS)
    created_at = START + timedelta(seconds=random.randint(0, DAY_RANGE * 86400))
    return (
        title, description, category, tags, duration_ms, bpm, fmt,
        random.choice(SAMPLE_RATES),
        f"library/{category.lower()}/{index:06d}.{fmt}",
        "library", None, random.choice(LICENSES), True, created_at, None,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=200_000)
    parser.add_argument("--dsn", default=os.getenv("DATABASE_URL", "postgresql://soundsnap:soundsnap@localhost:5432/soundsnap"))
    args = parser.parse_args()

    columns = (
        "title", "description", "category", "tags", "duration_ms", "bpm", "format",
        "sample_rate", "file_key", "source", "prompt_hash", "license", "is_active",
        "created_at", "indexed_at",
    )
    with psycopg.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE sounds RESTART IDENTITY CASCADE")
            with cur.copy(f"COPY sounds ({', '.join(columns)}) FROM STDIN") as copy:
                for i in range(args.count):
                    copy.write_row(make_row(i))
            cur.execute("SELECT count(*) FROM sounds")
            print(f"Inserted {cur.fetchone()[0]} sounds")


if __name__ == "__main__":
    main()
