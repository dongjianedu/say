import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import NoteList from './components/NoteList';
import NoteEditor from './components/NoteEditor';
import { useTranscriber } from "./hooks/useTranscriber";
import { AudioManager } from './components/AudioManager';

interface NoteVersion {
  content: string;
  timestamp: number;
  description: string;
}

interface Note {
  id: string;
  title: string;
  content: string;
  tags: string[];
  versions: NoteVersion[];
  created: number;
  lastEdited: number;
}

function App() {
    const transcriber = useTranscriber();
    const [notes, setNotes] = useState<Note[]>([]);
    const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);
    const [isLoaded, setIsLoaded] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [showNoteList, setShowNoteList] = useState(false);
    const [showInfo, setShowInfo] = useState(true);
    const lastTranscriptionRef = useRef<string | null>(null);

    useEffect(() => {
        const loadNotes = () => {
            const storedNotes = localStorage.getItem('notes');
            if (storedNotes) {
                try {
                    const parsedNotes = JSON.parse(storedNotes);
                    const migratedNotes = parsedNotes.map((note: any) => ({
                        ...note,
                        tags: note.tags || [],
                        versions: note.versions || [],
                        created: note.created || Date.now(),
                        lastEdited: note.lastEdited || Date.now()
                    }));
                    setNotes(migratedNotes);
                } catch (error) {
                    console.error('Error parsing stored notes:', error);
                }
            }
            setIsLoaded(true);
        };

        loadNotes();
    }, []);

    const saveNotes = useCallback((notesToSave: Note[]) => {
        localStorage.setItem('notes', JSON.stringify(notesToSave));
    }, []);

    const updateNotes = useCallback((newNotes: Note[]) => {
        setNotes(newNotes);
        saveNotes(newNotes);
    }, [saveNotes]);

    const handleCreateNote = useCallback(() => {
        const now = Date.now();
        const newNote: Note = {
            id: now.toString(),
            title: '新笔记',
            content: '',
            tags: [],
            versions: [],
            created: now,
            lastEdited: now
        };
        updateNotes([...notes, newNote]);
        setSelectedNoteId(newNote.id);
        return newNote.id;
    }, [notes, updateNotes]);

    const handleTranscriptionComplete = useCallback((text: string) => {
        setShowInfo(false);
        // Only create a new note if this is a new transcription
        if (text !== lastTranscriptionRef.current) {
            lastTranscriptionRef.current = text;
            const now = Date.now();
            const newNote: Note = {
                id: now.toString(),
                title: '转录笔记',
                content: text,
                tags: [],
                versions: [],
                created: now,
                lastEdited: now
            };
            updateNotes([...notes, newNote]);
            setSelectedNoteId(newNote.id);
            setShowNoteList(true);
        }
    }, [notes, updateNotes]);

    const handleDeleteNote = useCallback((id: string) => {
        const updatedNotes = notes.filter(note => note.id !== id);
        updateNotes(updatedNotes);
        if (selectedNoteId === id) {
            setSelectedNoteId(null);
        }
    }, [notes, selectedNoteId, updateNotes]);

    const handleUpdateNote = useCallback((updatedNote: Note) => {
        const updatedNotes = notes.map(note => 
            note.id === updatedNote.id ? { ...updatedNote, lastEdited: Date.now() } : note
        );
        updateNotes(updatedNotes);
    }, [notes, updateNotes]);

    const handleSaveVersion = useCallback((noteId: string, description: string) => {
        const note = notes.find(n => n.id === noteId);
        if (note) {
            const newVersion: NoteVersion = {
                content: note.content,
                timestamp: Date.now(),
                description
            };
            const updatedNote = {
                ...note,
                versions: [...note.versions, newVersion],
                lastEdited: Date.now()
            };
            handleUpdateNote(updatedNote);
        }
    }, [notes, handleUpdateNote]);

    const handleRestoreVersion = useCallback((noteId: string, version: NoteVersion) => {
        const note = notes.find(n => n.id === noteId);
        if (note) {
            const updatedNote = {
                ...note,
                content: version.content,
                lastEdited: Date.now()
            };
            handleUpdateNote(updatedNote);
        }
    }, [notes, handleUpdateNote]);

    const handleUpdateTags = useCallback((noteId: string, tags: string[]) => {
        const note = notes.find(n => n.id === noteId);
        if (note) {
            const updatedNote = {
                ...note,
                tags,
                lastEdited: Date.now()
            };
            handleUpdateNote(updatedNote);
        }
    }, [notes, handleUpdateNote]);

    const handleExportNotes = useCallback(() => {
        const notesBlob = new Blob([JSON.stringify(notes, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(notesBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'scribe-notes-export.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, [notes]);

    const handleImportNotes = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    const importedNotes = JSON.parse(e.target?.result as string);
                    if (Array.isArray(importedNotes) && importedNotes.every(note => 
                        typeof note === 'object' && 
                        'id' in note && 
                        'title' in note && 
                        'content' in note
                    )) {
                        const now = Date.now();
                        const migratedNotes = importedNotes.map(note => ({
                            ...note,
                            tags: note.tags || [],
                            versions: note.versions || [],
                            created: note.created || now,
                            lastEdited: note.lastEdited || now
                        }));
                        updateNotes(migratedNotes);
                    } else {
                        alert('无效的笔记格式');
                    }
                } catch (error) {
                    console.error('Error importing notes:', error);
                    alert('导入笔记出错');
                }
            };
            reader.readAsText(file);
        }
    }, [updateNotes]);

    const filteredNotes = useMemo(() => {
        const searchLower = searchQuery.toLowerCase();
        return notes.filter(note => {
            return (
                note.title.toLowerCase().includes(searchLower) ||
                note.content.toLowerCase().includes(searchLower) ||
                note.tags.some(tag => tag.toLowerCase().includes(searchLower))
            );
        })
    }, [notes, searchQuery]);

    if (!isLoaded) {
        return <div>加载中...</div>;
    }

    return (
        <div className='flex flex-col min-h-screen bg-slate-50'>
            <header className='bg-slate-800 text-white p-4 shadow-lg'>
                <div className="flex justify-between items-center">
                    <div className="flex items-center gap-4">
                        <h1 className='text-3xl font-bold'>Say</h1>
                        <button
                            onClick={() => setShowNoteList(!showNoteList)}
                            className="px-3 py-1 text-sm bg-slate-700 hover:bg-slate-600 rounded-md transition-colors"
                        >
                            {showNoteList ? '隐藏笔记' : '显示笔记'}
                        </button>
                    </div>
                </div>
            </header>
            <main className='flex-grow flex flex-col md:flex-row'>
                {showNoteList && (
                    <aside className='w-full md:w-72 bg-white border-b md:border-r border-slate-200 p-4 overflow-y-auto'>
                        <NoteList
                            notes={filteredNotes}
                            selectedNoteId={selectedNoteId}
                            onSelectNote={setSelectedNoteId}
                            onDeleteNote={handleDeleteNote}
                            onCreateNote={handleCreateNote}
                            searchQuery={searchQuery}
                            onSearchChange={setSearchQuery}
                            onExportNotes={handleExportNotes}
                            onImportNotes={handleImportNotes}
                        />
                    </aside>
                )}
                <section className={`flex-grow p-2 md:p-4 ${showNoteList ? 'md:w-[calc(100%-18rem)]' : 'w-full'}`}>
                    <div className="max-w-4xl mx-auto space-y-4 md:space-y-6">
                        <div className="bg-white rounded-xl shadow-lg p-4 md:p-6">
                            <h2 className="text-xl md:text-2xl font-semibold mb-4">快速录音</h2>
                            <AudioManager 
                                transcriber={transcriber}
                                onTranscriptionComplete={handleTranscriptionComplete}
                            />
                        </div>

                        {showInfo && (
                            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 md:p-6">
    <h3 className="text-base md:text-lg font-semibold text-blue-900 mb-2">欢迎使用 Say！</h3>
    <p className="text-sm md:text-base text-blue-800">
        使用 AI 轻松录制并将音频文件转录为文本。开始录制时，
        系统会下载一个小型语言模型到您的设备。所有处理都在本地私密完成。
    </p>
    <ul className="text-sm md:text-base list-disc list-inside pl-4 text-blue-800 md:p-6 p-6">
        <li>🎙️ 高质量的本地 Whisper 语音识别（tiny 或 base 模型）</li>
        <li>📂 转录录音、本地和网络音频文件</li>
        <li>📝 富文本编辑、笔记管理和版本控制</li>
        <li>✍️ T5 驱动的 AI 笔记摘要</li>
        <li>🔄 随时导出和导入所有笔记</li>
    </ul>
</div>
                        )}

                        {selectedNoteId && (
                            <div className="bg-white rounded-xl shadow-lg p-4 md:p-6">
                                <NoteEditor
                                    note={notes.find(note => note.id === selectedNoteId)!}
                                    onUpdateNote={handleUpdateNote}
                                    onSaveVersion={handleSaveVersion}
                                    onRestoreVersion={handleRestoreVersion}
                                    onUpdateTags={handleUpdateTags}
                                    transcriber={transcriber}
                                    hasMicrophonePermission={true}
                                />
                            </div>
                        )}
                    </div>
                </section>
            </main>
        </div>
    );
}

export default App;
