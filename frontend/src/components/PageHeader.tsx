import React from 'react';

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  sticky?: boolean;
}

const PageHeader: React.FC<PageHeaderProps> = ({ 
  title, 
  description, 
  actions, 
  sticky = true 
}) => {
  return (
    <div className={`
      w-full pb-8 pt-2
      ${sticky ? 'sticky top-0 z-30' : ''}
    `}>
      {/* Background Blur for Sticky Header */}
      {sticky && (
        <div className="absolute inset-0 -top-10 bg-slate-50/80 dark:bg-slate-950/80 backdrop-blur-md -z-10 border-b border-transparent" />
      )}

      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div className="space-y-1">
          <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            {title}
          </h1>
          {description && (
            <p className="text-sm font-medium text-slate-500 dark:text-slate-400 max-w-2xl">
              {description}
            </p>
          )}
        </div>

        {actions && (
          <div className="flex items-center gap-3 shrink-0">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
};

export default PageHeader;
