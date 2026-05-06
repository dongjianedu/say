import React, { ChangeEvent } from 'react';

interface ModelOption {
    id: string;
    name: string;
    description: string;
    isEnglishOnly: boolean;
    size: 'tiny' | 'small' | 'base' | 'medium' | 'large' | 'large-v2';
    isBeta?: boolean;
}

const modelOptions: ModelOption[] = [
    {
        id: 'Xenova/whisper-tiny.en',
        name: 'Tiny (英文)',
        description: '快速、轻量，针对英文转录优化的模型',
        isEnglishOnly: true,
        size: 'tiny'
    },
    {
        id: 'Xenova/whisper-tiny',
        name: 'Tiny (多语言)',
        description: '快速、轻量，支持多语言转录的模型',
        isEnglishOnly: false,
        size: 'tiny'
    },
    {
        id: 'Xenova/whisper-small.en',
        name: 'Small (英文)',
        description: '性能均衡的英文转录模型',
        isEnglishOnly: true,
        size: 'small'
    },
    {
        id: 'Xenova/whisper-small',
        name: 'Small (多语言)',
        description: '性能均衡，支持多语言转录的模型',
        isEnglishOnly: false,
        size: 'small'
    },
    {
        id: 'Xenova/whisper-base.en',
        name: 'Base (英文)',
        description: '标准英文转录模型',
        isEnglishOnly: true,
        size: 'base'
    },
    {
        id: 'Xenova/whisper-base',
        name: 'Base (多语言)',
        description: '标准模型，支持多语言转录',
        isEnglishOnly: false,
        size: 'base'
    },
    {
        id: 'Xenova/whisper-medium.en',
        name: 'Medium (英文)',
        description: '高精度英文转录模型',
        isEnglishOnly: true,
        size: 'medium'
    },
    {
        id: 'Xenova/whisper-large',
        name: 'Large',
        description: '最高精度的多语言转录模型',
        isEnglishOnly: false,
        size: 'large'
    },
    {
        id: 'Xenova/whisper-large-v2',
        name: 'Large V2',
        description: '最新版本，精度进一步提升',
        isEnglishOnly: false,
        size: 'large-v2'
    },
    {
        id: 'Xenova/nb-whisper-tiny-beta',
        name: 'Tiny Beta',
        description: '实验性 tiny 模型，包含新特性',
        isEnglishOnly: false,
        size: 'tiny',
        isBeta: true
    },
    {
        id: 'Xenova/nb-whisper-small-beta',
        name: 'Small Beta',
        description: '实验性 small 模型，包含新特性',
        isEnglishOnly: false,
        size: 'small',
        isBeta: true
    },
    {
        id: 'Xenova/nb-whisper-base-beta',
        name: 'Base Beta',
        description: '实验性 base 模型，包含新特性',
        isEnglishOnly: false,
        size: 'base',
        isBeta: true
    },
    {
        id: 'Xenova/nb-whisper-medium-beta',
        name: 'Medium Beta',
        description: '实验性 medium 模型，包含新特性',
        isEnglishOnly: false,
        size: 'medium',
        isBeta: true
    }
];

interface Props {
    selectedModel: string;
    onModelChange: (modelId: string) => void;
    className?: string;
}

export function ModelSelector({ selectedModel, onModelChange, className = '' }: Props): React.ReactElement {
    const handleChange = (e: ChangeEvent<HTMLSelectElement>) => {
        onModelChange(e.target.value);
    };

    return (
        <div className={`space-y-2 ${className}`}>
            <label htmlFor="model-select" className="block text-sm font-medium text-slate-600">
                转录模型
            </label>
            <select
                id="model-select"
                value={selectedModel}
                onChange={handleChange}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-slate-700"
            >
                {modelOptions.map((option) => (
                    <option key={option.id} value={option.id}>
                        {option.name} {option.isBeta ? '(Beta)' : ''} - {option.description}
                    </option>
                ))}
            </select>
            <p className="text-sm text-slate-500">
                {modelOptions.find(m => m.id === selectedModel)?.isEnglishOnly 
                    ? '此模型仅针对英文进行优化。'
                    : '此模型支持多种语言。'}
            </p>
        </div>
    );
}
