import React from 'react';
import { Moon, Sun } from 'lucide-react';
import { useTheme } from './ThemeProvider';
import { motion } from 'framer-motion';

export const ThemeToggle: React.FC = () => {
  const { theme, toggleTheme } = useTheme();

  return (
    <motion.button
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      onClick={toggleTheme}
      className="p-2 rounded-full bg-slate-200 dark:bg-white/10 text-slate-800 dark:text-emerald-400 hover:bg-slate-300 dark:hover:bg-white/20 transition-colors shadow-sm dark:shadow-[0_0_15px_rgba(16,185,129,0.3)] border border-slate-300 dark:border-emerald-500/30 font-sans"
      aria-label="Toggle Theme"
    >
      {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
    </motion.button>
  );
};
