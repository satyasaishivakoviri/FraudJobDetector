import React, { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export interface ImageGenerationLoaderProps {
  effect?: "scale-wave" | "shimmer" | "wave" | "none";
  easing?: "ease-in-out" | "linear" | "ease-in" | "ease-out" | ((t: number) => number);
  text?: string;
  cellSize?: number;
  gap?: number;
  bandHeight?: number;
  scaleAmplitude?: number;
  colors?: string[];
  className?: string;
  subMessages?: string[];
  subMessageInterval?: number;
}

export const ImageGenerationLoader: React.FC<ImageGenerationLoaderProps> = ({
  effect = "scale-wave",
  easing = "ease-in-out",
  text = "Analyzing Job Offer",
  cellSize = 3,
  gap = 1,
  bandHeight = 48,
  scaleAmplitude = 0.75,
  colors = ["#34d399", "#0b3b2a"],
  className,
  subMessages = [
    "Querying MCA corporate registrations",
    "Auditing GSTN taxpayer status",
    "Verifying domain WHOIS and mail servers",
    "Evaluating multi-factor risk rules",
  ],
  subMessageInterval = 1800,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [activeMessageIndex, setActiveMessageIndex] = useState(0);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  // Check user preference for reduced motion
  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mediaQuery.matches);
    const handler = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    mediaQuery.addEventListener("change", handler);
    return () => mediaQuery.removeEventListener("change", handler);
  }, []);

  // Cycle secondary informational messages
  useEffect(() => {
    if (!subMessages || subMessages.length === 0) return;
    const interval = setInterval(() => {
      setActiveMessageIndex((prev) => (prev + 1) % subMessages.length);
    }, subMessageInterval);
    return () => clearInterval(interval);
  }, [subMessages, subMessageInterval]);

  // Parse color hex to RGB
  const parseHex = (hex: string): [number, number, number] => {
    let cleanHex = hex.replace("#", "");
    if (cleanHex.length === 3) {
      cleanHex = cleanHex.split("").map((c) => c + c).join("");
    }
    const num = parseInt(cleanHex, 16);
    return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
  };

  const color1 = parseHex(colors[0] || "#34d399");
  const color2 = parseHex(colors[1] || "#0b3b2a");

  // Canvas animation logic
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let startTime: number | null = null;
    const duration = 2400; // ms per cycle

    const getEasing = (t: number): number => {
      if (typeof easing === "function") return easing(t);
      switch (easing) {
        case "linear":
          return t;
        case "ease-in":
          return t * t;
        case "ease-out":
          return t * (2 - t);
        case "ease-in-out":
        default:
          return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
      }
    };

    const handleResize = () => {
      const rect = container.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(rect.width * dpr);
      canvas.height = Math.floor(rect.height * dpr);
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      ctx.scale(dpr, dpr);
    };

    handleResize();
    const resizeObserver = new ResizeObserver(() => handleResize());
    resizeObserver.observe(container);

    const render = (currentTime: number) => {
      if (!startTime) startTime = currentTime;
      const elapsed = currentTime - startTime;

      const rect = container.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;

      ctx.clearRect(0, 0, width, height);

      // Deep dark green canvas base matching Glyph Portal
      const bgGrad = ctx.createLinearGradient(0, 0, width, height);
      bgGrad.addColorStop(0, "rgba(7, 26, 19, 0.98)");
      bgGrad.addColorStop(1, "rgba(11, 40, 29, 0.99)");
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, width, height);

      const step = cellSize + gap;
      const cols = Math.floor(width / step);
      const rows = Math.floor(height / step);
      const offsetX = (width - (cols * step - gap)) / 2;
      const offsetY = (height - (rows * step - gap)) / 2;

      // Scan position
      const cycleProgress = (elapsed % duration) / duration;
      const easedProgress = prefersReducedMotion ? 0.5 : getEasing(cycleProgress);
      const scanY = -bandHeight + easedProgress * (height + bandHeight * 2);

      // Render cells
      for (let r = 0; r < rows; r++) {
        const cy = offsetY + r * step;
        const distToScan = Math.abs(cy - scanY);
        const inBand = distToScan < bandHeight;

        for (let c = 0; c < cols; c++) {
          const cx = offsetX + c * step;

          let size = cellSize;
          let rVal = color2[0];
          let gVal = color2[1];
          let bVal = color2[2];
          let alpha = 0.12;

          if (inBand) {
            const intensity = 1 - distToScan / bandHeight;

            if (effect === "scale-wave") {
              const wave = Math.sin(c * 0.25 + elapsed * 0.005);
              const waveWeight = Math.max(0, (wave + 1) * 0.5);
              const scale = 1 + waveWeight * intensity * scaleAmplitude;
              size = cellSize * scale;

              // Color mix between emerald highlight and deep pine green
              const mix = waveWeight * intensity;
              rVal = Math.round(color2[0] + (color1[0] - color2[0]) * mix);
              gVal = Math.round(color2[1] + (color1[1] - color2[1]) * mix);
              bVal = Math.round(color2[2] + (color1[2] - color2[2]) * mix);
              alpha = 0.35 + intensity * 0.65;
            } else if (effect === "wave") {
              const wave = Math.sin(c * 0.2 + elapsed * 0.004);
              const mix = Math.max(0, wave) * intensity;
              rVal = Math.round(color2[0] + (color1[0] - color2[0]) * mix);
              gVal = Math.round(color2[1] + (color1[1] - color2[1]) * mix);
              bVal = Math.round(color2[2] + (color1[2] - color2[2]) * mix);
              alpha = 0.3 + intensity * 0.6;
            } else if (effect === "shimmer") {
              alpha = 0.4 + intensity * 0.55;
              rVal = color1[0];
              gVal = color1[1];
              bVal = color1[2];
            } else {
              alpha = 0.3 + intensity * 0.4;
            }
          }

          ctx.fillStyle = `rgba(${rVal}, ${gVal}, ${bVal}, ${alpha})`;
          ctx.beginPath();
          ctx.rect(cx - (size - cellSize) / 2, cy - (size - cellSize) / 2, size, size);
          ctx.fill();
        }
      }

      // Draw subtle luminous emerald scanline band
      if (!prefersReducedMotion && scanY > -bandHeight && scanY < height + bandHeight) {
        const bandGrad = ctx.createLinearGradient(0, scanY - bandHeight, 0, scanY + bandHeight);
        bandGrad.addColorStop(0, "rgba(52, 211, 153, 0)");
        bandGrad.addColorStop(0.5, "rgba(52, 211, 153, 0.22)");
        bandGrad.addColorStop(1, "rgba(52, 211, 153, 0)");
        ctx.fillStyle = bandGrad;
        ctx.fillRect(0, scanY - bandHeight, width, bandHeight * 2);

        // Core laser trace
        ctx.fillStyle = "rgba(52, 211, 153, 0.85)";
        ctx.fillRect(0, scanY, width, 1.5);
      }

      if (!prefersReducedMotion) {
        animationFrameId = requestAnimationFrame(render);
      }
    };

    animationFrameId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animationFrameId);
      resizeObserver.disconnect();
    };
  }, [cellSize, gap, bandHeight, scaleAmplitude, colors, effect, easing, prefersReducedMotion]);

  const currentSubMessage = subMessages[activeMessageIndex] || "Running verification checks...";

  return (
    <div
      ref={containerRef}
      role="status"
      aria-live="polite"
      className={cn(
        "relative w-full max-w-2xl mx-auto rounded-2xl overflow-hidden border border-emerald-500/35",
        "bg-[#071a13] text-[#fbfbfa] shadow-[0_20px_60px_rgba(11,59,42,0.35),0_0_30px_rgba(52,211,153,0.15)]",
        "p-8 sm:p-12 flex flex-col items-center justify-center min-h-[340px]",
        className
      )}
    >
      {/* Background HTML5 Canvas Grid */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 pointer-events-none"
        aria-hidden="true"
      />

      {/* Decorative Corner Reticle Accents */}
      <div className="absolute top-3 left-3 w-3.5 h-3.5 border-t-2 border-l-2 border-emerald-400/80 pointer-events-none" />
      <div className="absolute top-3 right-3 w-3.5 h-3.5 border-t-2 border-r-2 border-emerald-400/80 pointer-events-none" />
      <div className="absolute bottom-3 left-3 w-3.5 h-3.5 border-b-2 border-l-2 border-emerald-400/80 pointer-events-none" />
      <div className="absolute bottom-3 right-3 w-3.5 h-3.5 border-b-2 border-r-2 border-emerald-400/80 pointer-events-none" />

      {/* Foreground Content */}
      <div className="relative z-10 flex flex-col items-center text-center max-w-md space-y-4">
        {/* Radar Icon / Visual Indicator */}
        <div className="relative flex items-center justify-center w-16 h-16 rounded-full bg-[#0b3b2a]/90 border border-emerald-500/50 shadow-[0_0_24px_rgba(52,211,153,0.35)]">
          <div className="absolute inset-1 rounded-full border border-emerald-400/40 animate-ping opacity-60" />
          <svg
            className="w-8 h-8 text-emerald-300"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
            />
          </svg>
        </div>

        {/* Main Verification Text */}
        <div className="space-y-1">
          <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-white drop-shadow-[0_2px_12px_rgba(52,211,153,0.4)]">
            {text}
          </h3>
          <p className="text-xs uppercase tracking-widest font-mono text-emerald-400 font-semibold">
            Corporate Due Diligence Engine
          </p>
        </div>

        {/* Rotating Secondary Status Pill */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#082d22]/90 border border-emerald-500/35 shadow-inner">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
          </span>
          <span className="text-xs font-medium text-emerald-100 transition-opacity duration-300">
            {currentSubMessage}
          </span>
        </div>

        {/* Screen Reader Announcement */}
        <div className="sr-only" aria-live="polite" aria-atomic="true">
          {text}. {currentSubMessage}
        </div>
      </div>
    </div>
  );
};

export default ImageGenerationLoader;
