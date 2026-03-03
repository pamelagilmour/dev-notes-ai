'use client';

import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface KnowledgeEntry {
  id: number;
  title: string;
  content: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export default function DashboardPage() {
  const { user, token, logout, loading } = useAuth();
  const router = useRouter();

  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editingEntry, setEditingEntry] = useState<KnowledgeEntry | null>(null);

  const [chatMessage, setChatMessage] = useState('');
  const [chatResponse, setChatResponse] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<{ role: string, content: string }[]>([]);

  // Form state
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [tags, setTags] = useState('');
  const [formError, setFormError] = useState('');
  const [formLoading, setFormLoading] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user && token) {
      fetchEntries();
    }
  }, [user, token]);

  const fetchEntries = async () => {
    try {
      const response = await fetch(`${API_URL}/api/entries`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        console.error('Failed to fetch entries, status:', response.status);
        setEntries([]);
        return;
      }

      const data = await response.json();
      console.log('Fetched entries data:', data);

      // Make sure data is an array
      if (Array.isArray(data)) {
        setEntries(data);
      } else {
        console.error('Expected array, got:', typeof data, data);
        setEntries([]);
      }
    } catch (error) {
      console.error('Failed to fetch entries:', error);
      setEntries([]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    setFormLoading(true);

    try {
      const tagsArray = tags.split(',').map(t => t.trim()).filter(t => t);
      const url = editingEntry
        ? `${API_URL}/api/entries/${editingEntry.id}`
        : `${API_URL}/api/entries`;

      const method = editingEntry ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ title, content, tags: tagsArray })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save entry');
      }

      // Reset form and refresh entries
      setTitle('');
      setContent('');
      setTags('');
      setShowForm(false);
      setEditingEntry(null);
      await fetchEntries();
    } catch (err: any) {
      setFormError(err.message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleEdit = (entry: KnowledgeEntry) => {
    setEditingEntry(entry);
    setTitle(entry.title);
    setContent(entry.content);
    setTags(entry.tags.join(', '));
    setShowForm(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this entry?')) return;

    try {
      const response = await fetch(`${API_URL}/api/entries/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        await fetchEntries();
      }
    } catch (error) {
      console.error('Failed to delete entry:', error);
    }
  };

  const cancelForm = () => {
    setShowForm(false);
    setEditingEntry(null);
    setTitle('');
    setContent('');
    setTags('');
    setFormError('');
  };

  const handleChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatMessage.trim()) return;

    setChatLoading(true);
    const userMessage = chatMessage;
    setChatMessage('');

    // Add user message to history
    setChatHistory(prev => [...prev, { role: 'user', content: userMessage }]);

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ message: userMessage })
      });

      const data = await response.json();

      // Add AI response to history
      setChatHistory(prev => [...prev, { role: 'assistant', content: data.response }]);

    } catch (error) {
      setChatHistory(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.'
      }]);
    } finally {
      setChatLoading(false);
    }
  };


  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p>Loading...</p>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-bold text-gray-950">Dev Notes AI</h1>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-gray-700">{user.email}</span>
              <button
                onClick={logout}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">

          {/* Header with Add Button */}
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-950">Your Knowledge Entries</h2>
            {!showForm && (
              <button
                onClick={() => setShowForm(true)}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                + New Entry
              </button>
            )}
          </div>

          {/* Create/Edit Form */}
          {showForm && (
            <div className="bg-white shadow rounded-lg p-6 mb-6">
              <h3 className="text-xl font-semibold mb-4 text-gray-950">
                {editingEntry ? 'Edit Entry' : 'New Entry'}
              </h3>

              {formError && (
                <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded mb-4">
                  {formError}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Title
                  </label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-950"
                    placeholder="Entry title..."
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Content
                  </label>
                  <textarea
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    required
                    rows={6}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-950"
                    placeholder="Write your knowledge entry here..."
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Tags (comma separated)
                  </label>
                  <input
                    type="text"
                    value={tags}
                    onChange={(e) => setTags(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-950"
                    placeholder="react, typescript, tutorial"
                  />
                </div>

                <div className="flex gap-3">
                  <button
                    type="submit"
                    disabled={formLoading}
                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                  >
                    {formLoading ? 'Saving...' : editingEntry ? 'Update' : 'Create'}
                  </button>
                  <button
                    type="button"
                    onClick={cancelForm}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Entries List */}
          {entries.length === 0 ? (
            <div className="bg-white shadow rounded-lg p-12 text-center">
              <p className="text-gray-500 text-lg mb-4">No entries yet!</p>
              <p className="text-gray-400">Click "New Entry" to create your first knowledge entry.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {entries.map((entry) => (
                <div key={entry.id} className="bg-white shadow rounded-lg p-6">
                  <div className="flex justify-between items-start mb-3">
                    <h3 className="text-xl font-semibold text-gray-950">{entry.title}</h3>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleEdit(entry)}
                        className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(entry.id)}
                        className="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200"
                      >
                        Delete
                      </button>
                    </div>
                  </div>

                  <p className="text-gray-700 whitespace-pre-wrap mb-3">{entry.content}</p>

                  {entry.tags.length > 0 && (
                    <div className="flex gap-2 flex-wrap mb-2">
                      {entry.tags.map((tag, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-1 bg-gray-100 text-gray-700 text-sm rounded"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  <p className="text-sm text-gray-500">
                    Created: {new Date(entry.created_at).toLocaleDateString()}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="mt-8 bg-white shadow rounded-lg p-6">
          <h2 className="text-2xl font-bold mb-4 text-gray-950">🤖 Ask AI About Your Knowledge Base</h2>

          {/* Chat History */}
          <div className="mb-4 space-y-3 max-h-96 overflow-y-auto">
            {chatHistory.length === 0 && (
              <p className="text-gray-500 text-center py-8">
                Ask me anything about your knowledge base!
              </p>
            )}
            {chatHistory.map((msg, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-lg ${msg.role === 'user'
                    ? 'bg-blue-50 text-blue-900 ml-8'
                    : 'bg-gray-50 text-gray-900 mr-8'
                  }`}
              >
                <p className="text-xs font-semibold mb-1">
                  {msg.role === 'user' ? '👤 You' : '🤖 AI'}
                </p>
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            ))}
            {chatLoading && (
              <div className="bg-gray-50 text-gray-900 mr-8 p-3 rounded-lg">
                <p className="text-xs font-semibold mb-1">🤖 AI</p>
                <p className="text-gray-500">Thinking...</p>
              </div>
            )}
          </div>

          {/* Chat Input */}
          <form onSubmit={handleChat} className="flex gap-2">
            <input
              type="text"
              value={chatMessage}
              onChange={(e) => setChatMessage(e.target.value)}
              placeholder="Ask about your knowledge base..."
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
              disabled={chatLoading}
            />
            <button
              type="submit"
              disabled={chatLoading || !chatMessage.trim()}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {chatLoading ? '...' : 'Ask'}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}