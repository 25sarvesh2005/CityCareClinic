import React, { useState } from "react";
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight, Sparkles } from "lucide-react";
import { format, parseISO, addDays, isSameDay } from "date-fns";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

interface AestheticDatePickerProps {
  selectedDate: string; // YYYY-MM-DD
  onDateChange: (newDateISO: string) => void;
  minDateISO?: string;
  maxDateISO?: string;
  unavailableDates?: string[];
  label?: string;
}

export function AestheticDatePicker({
  selectedDate,
  onDateChange,
  minDateISO,
  maxDateISO,
  unavailableDates = [],
  label = "Select Consultation Date",
}: AestheticDatePickerProps) {
  const [popoverOpen, setPopoverOpen] = useState(false);

  const parsedSelected = parseISO(selectedDate);
  const minDate = minDateISO ? parseISO(minDateISO) : new Date();
  const maxDate = maxDateISO ? parseISO(maxDateISO) : addDays(new Date(), 7);

  // Generate 7 consecutive days starting from minDate for the quick strip
  const quickDays = Array.from({ length: 7 }).map((_, i) => addDays(minDate, i));

  const handleDaySelect = (day: Date | undefined) => {
    if (!day) return;
    const iso = format(day, "yyyy-MM-dd");
    onDateChange(iso);
    setPopoverOpen(false);
  };

  return (
    <div className="space-y-3">
      {/* Header with Title & Popover Calendar Trigger */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="size-4 text-cyan animate-pulse" />
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {label}
          </span>
        </div>

        {/* Calendar Popover Trigger */}
        <Popover open={popoverOpen} onOpenChange={setPopoverOpen}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className={cn(
                "group inline-flex items-center gap-2 rounded-xl border border-glass-border bg-glass/80 px-3 py-1.5 text-xs font-medium backdrop-blur-xl transition-all duration-200 hover:border-cyan/50 hover:bg-cyan/10 active:scale-95 shadow-sm",
                popoverOpen && "border-cyan bg-cyan/15 text-cyan ring-2 ring-cyan/30",
              )}
            >
              <CalendarIcon className="size-3.5 text-cyan transition-transform group-hover:scale-110" />
              <span>{format(parsedSelected, "EEEE, MMM d, yyyy")}</span>
            </button>
          </PopoverTrigger>

          <PopoverContent className="w-auto p-0 border-none bg-transparent shadow-none" align="end">
            <Calendar
              mode="single"
              selected={parsedSelected}
              onSelect={handleDaySelect}
              disabled={(date) => date < minDate || date > maxDate}
              initialFocus
            />
          </PopoverContent>
        </Popover>
      </div>

      {/* 7-Day Interactive Quick Strip */}
      <div className="grid grid-cols-7 gap-1.5 sm:gap-2">
        {quickDays.map((dayDate) => {
          const isoString = format(dayDate, "yyyy-MM-dd");
          const isSelected = isSameDay(dayDate, parsedSelected);
          const isToday = isSameDay(dayDate, new Date());
          const isPast = dayDate < minDate;
          const isOff = unavailableDates.includes(isoString);

          return (
            <button
              key={isoString}
              type="button"
              disabled={isPast}
              onClick={() => onDateChange(isoString)}
              className={cn(
                "relative flex flex-col items-center justify-center rounded-2xl border p-2 transition-all duration-200 active:scale-95",
                isSelected
                  ? isOff
                    ? "border-destructive/80 bg-gradient-to-b from-rose-900/90 via-red-800/80 to-amber-900/90 text-white shadow-lg shadow-destructive/30 scale-[1.03] ring-2 ring-destructive/60"
                    : "border-transparent bg-gradient-to-b from-indigo-600/90 via-cyan-600/80 to-teal-500/90 text-white shadow-lg shadow-cyan-500/20 scale-[1.03] ring-2 ring-cyan-400/40"
                  : isOff
                    ? "border-destructive/40 bg-destructive/10 text-destructive hover:bg-destructive/20 hover:border-destructive/60"
                    : "border-glass-border/60 bg-glass/50 text-foreground hover:border-cyan/40 hover:bg-cyan/10 hover:-translate-y-0.5",
                isPast && "cursor-not-allowed opacity-30 line-through",
              )}
            >
              {/* OFF / Today Badge */}
              {isOff ? (
                <span
                  className={cn(
                    "mb-1 rounded-full px-1.5 py-0.5 text-[0.6rem] font-bold tracking-wider uppercase",
                    isSelected
                      ? "bg-white/20 text-white"
                      : "bg-destructive/20 text-destructive border border-destructive/40",
                  )}
                >
                  OFF
                </span>
              ) : isToday ? (
                <span
                  className={cn(
                    "mb-1 rounded-full px-1.5 py-0.5 text-[0.6rem] font-bold tracking-wider uppercase",
                    isSelected
                      ? "bg-white/20 text-white"
                      : "bg-cyan/20 text-cyan border border-cyan/30",
                  )}
                >
                  Today
                </span>
              ) : null}

              {/* Day Name (e.g. MON) */}
              <span
                className={cn(
                  "text-[0.65rem] font-semibold uppercase tracking-wider",
                  isSelected
                    ? "text-cyan-100"
                    : isOff
                      ? "text-destructive/80"
                      : "text-muted-foreground",
                )}
              >
                {format(dayDate, "EEE")}
              </span>

              {/* Day Number (e.g. 08) */}
              <span
                className={cn(
                  "text-base sm:text-lg font-bold tracking-tight mt-0.5",
                  isSelected ? "text-white" : isOff ? "text-destructive font-extrabold" : "text-foreground",
                )}
              >
                {format(dayDate, "dd")}
              </span>

              {/* Month (e.g. AUG) */}
              <span
                className={cn(
                  "text-[0.6rem] font-medium uppercase tracking-widest mt-0.5",
                  isSelected
                    ? "text-cyan-200"
                    : isOff
                      ? "text-destructive/70"
                      : "text-muted-foreground/70",
                )}
              >
                {format(dayDate, "MMM")}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
