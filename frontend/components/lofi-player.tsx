"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import {
  Play,
  Pause,
  SkipForward,
  SkipBack,
  Volume2,
  VolumeX,
  Music,
  Radio,
} from "lucide-react";

// Lofi streams/tracks - using free lofi radio streams
const LOFI_STATIONS = [
  {
    name: "Lofi Girl",
    url: "https://play.streamafrica.net/lofiradio",
  },
  {
    name: "Chillhop",
    url: "https://streams.ilovemusic.de/iloveradio17.mp3",
  },
  {
    name: "Box Lofi",
    url: "https://boxradio-edge-00.streamafrica.net/lofi",
  },
  {
    name: "Nightride FM",
    url: "https://stream.nightride.fm/nightride.m4a",
  },
];

export function LofiPlayer() {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [volume, setVolume] = useState(30);
  const [isMuted, setIsMuted] = useState(false);
  const [currentStation, setCurrentStation] = useState(0);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = isMuted ? 0 : volume / 100;
    }
  }, [volume, isMuted]);

  const togglePlay = async () => {
    if (!audioRef.current) return;

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      setIsLoading(true);
      try {
        await audioRef.current.play();
        setIsPlaying(true);
      } catch (error) {
        console.error("Failed to play audio:", error);
      } finally {
        setIsLoading(false);
      }
    }
  };

  const nextStation = () => {
    const next = (currentStation + 1) % LOFI_STATIONS.length;
    setCurrentStation(next);
    if (isPlaying && audioRef.current) {
      audioRef.current.src = LOFI_STATIONS[next].url;
      audioRef.current.play();
    }
  };

  const prevStation = () => {
    const prev = (currentStation - 1 + LOFI_STATIONS.length) % LOFI_STATIONS.length;
    setCurrentStation(prev);
    if (isPlaying && audioRef.current) {
      audioRef.current.src = LOFI_STATIONS[prev].url;
      audioRef.current.play();
    }
  };

  const toggleMute = () => {
    setIsMuted(!isMuted);
  };

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <audio ref={audioRef} src={LOFI_STATIONS[currentStation].url} preload="none" />

      {/* Collapsed View - Just a floating button */}
      {!isExpanded ? (
        <Button
          onClick={() => setIsExpanded(true)}
          className={`rounded-full h-12 w-12 shadow-lg ${
            isPlaying
              ? "bg-indigo-600 hover:bg-indigo-700 animate-pulse"
              : "bg-slate-800 hover:bg-slate-700 dark:bg-slate-700 dark:hover:bg-slate-600"
          }`}
        >
          <Music className="h-5 w-5" />
        </Button>
      ) : (
        /* Expanded Player */
        <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-700 p-4 w-72">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div
                className={`w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center ${
                  isPlaying ? "animate-spin" : ""
                }`}
                style={{ animationDuration: "3s" }}
              >
                <Radio className="h-4 w-4 text-white" />
              </div>
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">Now Playing</p>
                <p className="text-sm font-medium text-slate-900 dark:text-white">
                  {LOFI_STATIONS[currentStation].name}
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 text-slate-400 hover:text-slate-600"
              onClick={() => setIsExpanded(false)}
            >
              ×
            </Button>
          </div>

          {/* Visualizer Bar (decorative) */}
          <div className="flex items-end justify-center gap-0.5 h-8 mb-3">
            {[...Array(20)].map((_, i) => (
              <div
                key={i}
                className={`w-1 bg-gradient-to-t from-indigo-500 to-purple-500 rounded-full transition-all ${
                  isPlaying ? "animate-pulse" : ""
                }`}
                style={{
                  height: isPlaying ? `${Math.random() * 100}%` : "20%",
                  animationDelay: `${i * 50}ms`,
                  animationDuration: "300ms",
                }}
              />
            ))}
          </div>

          {/* Controls */}
          <div className="flex items-center justify-center gap-2 mb-3">
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9"
              onClick={prevStation}
            >
              <SkipBack className="h-4 w-4" />
            </Button>
            <Button
              onClick={togglePlay}
              className="h-12 w-12 rounded-full bg-indigo-600 hover:bg-indigo-700"
              disabled={isLoading}
            >
              {isLoading ? (
                <div className="h-5 w-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : isPlaying ? (
                <Pause className="h-5 w-5" />
              ) : (
                <Play className="h-5 w-5 ml-0.5" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9"
              onClick={nextStation}
            >
              <SkipForward className="h-4 w-4" />
            </Button>
          </div>

          {/* Volume */}
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 shrink-0"
              onClick={toggleMute}
            >
              {isMuted || volume === 0 ? (
                <VolumeX className="h-4 w-4" />
              ) : (
                <Volume2 className="h-4 w-4" />
              )}
            </Button>
            <Slider
              value={[isMuted ? 0 : volume]}
              max={100}
              step={1}
              className="flex-1"
              onValueChange={(value) => {
                setVolume(value[0]);
                if (value[0] > 0) setIsMuted(false);
              }}
            />
            <span className="text-xs text-slate-500 w-8 text-right">{volume}%</span>
          </div>

          {/* Station List */}
          <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-700">
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">Stations</p>
            <div className="grid grid-cols-2 gap-1">
              {LOFI_STATIONS.map((station, index) => (
                <button
                  key={station.name}
                  onClick={() => {
                    setCurrentStation(index);
                    if (isPlaying && audioRef.current) {
                      audioRef.current.src = station.url;
                      audioRef.current.play();
                    }
                  }}
                  className={`text-xs px-2 py-1.5 rounded-md transition-colors text-left truncate ${
                    index === currentStation
                      ? "bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300"
                      : "hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400"
                  }`}
                >
                  {station.name}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
