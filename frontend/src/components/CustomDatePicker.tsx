import React, { useState, useRef, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronLeft, ChevronRight, Calendar, X } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface CustomDatePickerProps {
  value: string; // YYYY-MM-DD
  onChange: (value: string) => void;
  label?: string;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
}

export const CustomDatePicker: React.FC<CustomDatePickerProps> = ({
  value,
  onChange,
  label,
  placeholder = 'Select date',
  className,
  disabled = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Parse initial date or default to today
  const initialDate = useMemo(() => {
    if (value) {
      const d = new Date(value);
      return isNaN(d.getTime()) ? new Date() : d;
    }
    return new Date();
  }, [value]);

  const [viewDate, setViewDate] = useState(new Date(initialDate.getFullYear(), initialDate.getMonth(), 1));

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const toggleOpen = () => {
    if (!disabled) {
      setIsOpen(!isOpen);
      if (!isOpen) {
        // Reset view date when opening
        setViewDate(new Date(initialDate.getFullYear(), initialDate.getMonth(), 1));
      }
    }
  };

  const handlePrevMonth = (e: React.MouseEvent) => {
    e.stopPropagation();
    setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1));
  };

  const handleNextMonth = (e: React.MouseEvent) => {
    e.stopPropagation();
    setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1));
  };

  const handleDateSelect = (day: number) => {
    const selected = new Date(viewDate.getFullYear(), viewDate.getMonth(), day);
    const offset = selected.getTimezoneOffset() * 60000;
    const localISODate = new Date(selected.getTime() - offset).toISOString().split('T')[0];
    onChange(localISODate);
    setIsOpen(false);
  };

  const daysInMonth = (year: number, month: number) => new Date(year, month + 1, 0).getDate();
  const firstDayOfMonth = (year: number, month: number) => new Date(year, month, 1).getDay();

  const calendarDays = useMemo(() => {
    const year = viewDate.getFullYear();
    const month = viewDate.getMonth();
    const totalDays = daysInMonth(year, month);
    const startDay = firstDayOfMonth(year, month);
    
    const days = [];
    // Previous month placeholders
    for (let i = 0; i < startDay; i++) {
      days.push({ day: 0, current: false });
    }
    // Current month days
    for (let i = 1; i <= totalDays; i++) {
      days.push({ day: i, current: true });
    }
    return days;
  }, [viewDate]);

  const monthName = viewDate.toLocaleString('default', { month: 'long' });
  const year = viewDate.getFullYear();

  const isSelected = (day: number) => {
    if (!value || day === 0) return false;
    const d = new Date(value);
    return d.getFullYear() === viewDate.getFullYear() && 
           d.getMonth() === viewDate.getMonth() && 
           d.getDate() === day;
  };

  const isToday = (day: number) => {
    if (day === 0) return false;
    const today = new Date();
    return today.getFullYear() === viewDate.getFullYear() && 
           today.getMonth() === viewDate.getMonth() && 
           today.getDate() === day;
  };

  return (
    <div className={cn('flex flex-col gap-1.5 w-full', className)} ref={containerRef}>
      {label && (
        <label className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest ml-1">
          {label}
        </label>
      )}
      <div className="relative">
        <button
          type="button"
          onClick={toggleOpen}
          disabled={disabled}
          className={cn(
            'flex items-center gap-3 w-full p-3 bg-slate-50/50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700 rounded-xl text-sm transition-all focus:ring-2 focus:ring-indigo-500/20 outline-none hover:border-indigo-500/50 text-left relative overflow-hidden',
            isOpen && 'border-indigo-500 ring-2 ring-indigo-500/20 bg-white dark:bg-slate-900',
            disabled && 'opacity-50 cursor-not-allowed grayscale'
          )}
        >
          <Calendar size={18} className={cn('text-slate-400 transition-colors', isOpen && 'text-indigo-500')} />
          <span className={cn('truncate font-medium flex-1', value ? 'text-slate-900 dark:text-white' : 'text-slate-400')}>
            {value ? new Date(value).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' }) : placeholder}
          </span>
          {value && !disabled && (
            <X 
              size={14} 
              className="text-slate-300 hover:text-rose-500 transition-colors cursor-pointer" 
              onClick={(e) => {
                e.stopPropagation();
                onChange('');
              }}
            />
          )}
        </button>

        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={{ duration: 0.15, ease: 'easeOut' }}
              className="absolute z-[100] w-[300px] mt-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl p-4 overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-4 px-1">
                <div className="flex flex-col">
                  <span className="text-sm font-black text-slate-900 dark:text-white leading-tight">{monthName}</span>
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{year}</span>
                </div>
                <div className="flex gap-1">
                  <button onClick={handlePrevMonth} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-slate-500 transition-colors">
                    <ChevronLeft size={16} />
                  </button>
                  <button onClick={handleNextMonth} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-slate-500 transition-colors">
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>

              {/* Day Labels */}
              <div className="grid grid-cols-7 mb-2">
                {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map(day => (
                  <span key={day} className="text-[10px] font-black text-slate-300 dark:text-slate-600 uppercase text-center">{day}</span>
                ))}
              </div>

              {/* Day Grid */}
              <div className="grid grid-cols-7 gap-1">
                {calendarDays.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => item.current && handleDateSelect(item.day)}
                    disabled={!item.current}
                    className={cn(
                      'aspect-square flex items-center justify-center rounded-lg text-xs font-bold transition-all relative',
                      !item.current && 'opacity-0 cursor-default',
                      item.current && !isSelected(item.day) && 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800',
                      isSelected(item.day) && 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/30 scale-110 z-10',
                      isToday(item.day) && !isSelected(item.day) && 'text-indigo-600 dark:text-indigo-400'
                    )}
                  >
                    {item.day > 0 ? item.day : ''}
                    {isToday(item.day) && !isSelected(item.day) && (
                      <span className="absolute bottom-1 w-1 h-1 rounded-full bg-indigo-500"></span>
                    )}
                  </button>
                ))}
              </div>
              
              {/* Footer Actions */}
              <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex justify-between">
                 <button 
                  onClick={() => {
                    const today = new Date();
                    const offset = today.getTimezoneOffset() * 60000;
                    onChange(new Date(today.getTime() - offset).toISOString().split('T')[0]);
                    setIsOpen(false);
                  }}
                  className="text-[10px] font-black text-indigo-600 dark:text-indigo-400 uppercase tracking-widest hover:underline"
                 >
                   Today
                 </button>
                 <button 
                  onClick={() => setIsOpen(false)}
                  className="text-[10px] font-black text-slate-400 uppercase tracking-widest hover:text-slate-600 transition-colors"
                 >
                   Close
                 </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};
