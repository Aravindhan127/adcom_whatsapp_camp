import React from 'react';
import { CustomSelect } from './CustomSelect';

export const COUNTRY_CODES = [
  { code: '+91', country: 'India', flag: '🇮🇳', iso: 'in' },
  { code: '+1', country: 'USA/Canada', flag: '🇺🇸', iso: 'us' },
  { code: '+44', country: 'UK', flag: '🇬🇧', iso: 'gb' },
  { code: '+971', country: 'UAE', flag: '🇦🇪', iso: 'ae' },
  { code: '+65', country: 'Singapore', flag: '🇸🇬', iso: 'sg' },
  { code: '+61', country: 'Australia', flag: '🇦🇺', iso: 'au' },
  { code: '+49', country: 'Germany', flag: '🇩🇪', iso: 'de' },
  { code: '+33', country: 'France', flag: '🇫🇷', iso: 'fr' },
  { code: '+81', country: 'Japan', flag: '🇯🇵', iso: 'jp' },
  { code: '+86', country: 'China', flag: '🇨🇳', iso: 'cn' },
  { code: '+966', country: 'Saudi Arabia', flag: '🇸🇦', iso: 'sa' },
  { code: '+94', country: 'Sri Lanka', flag: '🇱🇰', iso: 'lk' },
  { code: '+880', country: 'Bangladesh', flag: '🇧🇩', iso: 'bd' },
];

interface Props {
  value: string;
  onChange: (code: string) => void;
  disabled?: boolean;
}

const CountryCodeSelector: React.FC<Props> = ({ value, onChange, disabled }) => {
  return (
    <CustomSelect
      value={value}
      onChange={onChange}
      className="w-24"
      options={COUNTRY_CODES.map((c) => ({
        value: c.code,
        label: `${c.flag} ${c.code}`
      }))}
    />
  );
};

export default CountryCodeSelector;
