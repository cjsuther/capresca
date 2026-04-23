import { useState, useEffect, useRef, useCallback } from "react";
import {
  MessageCircle, Send, Paperclip, Search, Plus, X, UserPlus, Phone, AlertTriangle,
  Check, CheckCheck, Clock, Bot,
} from "lucide-react";
import clsx from "clsx";
import {
  getConversations, getMessages, sendMessage, sendMediaMessage,
  markConversationRead, createConversation, linkClient, getStats, searchClientes,
} from "../../../api/comunicacion";

function getToken() {
  try {
    const raw = sessionStorage.getItem("auth-storage");
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.state?.token || null;
  } catch { return null; }
}

function AuthImage({ src, alt, className, onClick }) {
  const [blobUrl, setBlobUrl] = useState(null);
  useEffect(() => {
    let revoke;
    const token = getToken();
    fetch(src, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        setBlobUrl(url);
        revoke = url;
      })
      .catch(() => {});
    return () => { if (revoke) URL.revokeObjectURL(revoke); };
  }, [src]);
  if (!blobUrl) return <div className={clsx(className, "bg-gray-700 animate-pulse")} style={{ height: 120 }} />;
  return <img src={blobUrl} alt={alt} className={className} onClick={onClick} />;
}

function fetchMediaWithAuth(url) {
  const token = getToken();
  fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    .then((r) => r.blob())
    .then((blob) => {
      const blobUrl = URL.createObjectURL(blob);
      window.open(blobUrl, "_blank");
    });
}

function timeAgo(dateStr) {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Ahora";
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return "Ayer";
  return `${days}d`;
}

function StatusIcon({ status }) {
  if (status === "READ") return <CheckCheck size={14} className="text-blue-500" />;
  if (status === "DELIVERED") return <CheckCheck size={14} className="text-gray-400" />;
  if (status === "SENT") return <Check size={14} className="text-gray-400" />;
  if (status === "FAILED") return <AlertTriangle size={14} className="text-red-400" />;
  return <Clock size={14} className="text-gray-300" />;
}

export default function ComunicacionPage() {
  const [conversations, setConversations] = useState([]);
  const [selectedConv, setSelectedConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(false);
  const [msgLoading, setMsgLoading] = useState(false);
  const [sendLoading, setSendLoading] = useState(false);
  const [stats, setStats] = useState(null);

  // New conversation modal
  const [showNewConv, setShowNewConv] = useState(false);
  const [clientSearch, setClientSearch] = useState("");
  const [clientResults, setClientResults] = useState([]);
  const [selectedClient, setSelectedClient] = useState(null);
  const [selectedPhone, setSelectedPhone] = useState("");

  // Link client modal
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [linkSearch, setLinkSearch] = useState("");
  const [linkResults, setLinkResults] = useState([]);
  const [linkLoading, setLinkLoading] = useState(false);

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const prevMsgCountRef = useRef(0);

  const loadConversations = useCallback(async () => {
    setLoading(true);
    try {
      const params = { per_page: 50 };
      if (searchText) params.search = searchText;
      const data = await getConversations(params);
      setConversations(data.data);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [searchText]);

  const loadMessages = useCallback(async (convId) => {
    if (prevMsgCountRef.current === 0) setMsgLoading(true);
    try {
      const data = await getMessages(convId, { limit: 100 });
      setMessages((prev) => {
        if (prev.length === data.data.length && prev.length > 0 &&
            prev[prev.length - 1]?.id === data.data[data.data.length - 1]?.id) {
          return prev;
        }
        return data.data;
      });
      markConversationRead(convId).catch(() => {});
    } catch {
      setMessages([]);
    } finally {
      setMsgLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConversations();
    getStats().then(setStats).catch(() => {});
  }, [loadConversations]);

  useEffect(() => {
    if (selectedConv) loadMessages(selectedConv.id);
  }, [selectedConv, loadMessages]);

  useEffect(() => {
    if (messages.length !== prevMsgCountRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      prevMsgCountRef.current = messages.length;
    }
  }, [messages]);

  // Polling every 10s
  useEffect(() => {
    const interval = setInterval(() => {
      loadConversations();
      if (selectedConv) loadMessages(selectedConv.id);
    }, 10000);
    return () => clearInterval(interval);
  }, [selectedConv, loadConversations, loadMessages]);

  const handleSend = async () => {
    if (!newMessage.trim() || !selectedConv) return;
    setSendLoading(true);
    try {
      await sendMessage(selectedConv.id, { content: newMessage.trim() });
      setNewMessage("");
      await loadMessages(selectedConv.id);
      await loadConversations();
    } catch {
      // handle error
    } finally {
      setSendLoading(false);
    }
  };

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !selectedConv) return;
    setSendLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      await sendMediaMessage(selectedConv.id, formData);
      await loadMessages(selectedConv.id);
      await loadConversations();
    } catch {
      // handle error
    } finally {
      setSendLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewConversation = async () => {
    if (!selectedClient || !selectedPhone) return;
    try {
      const conv = await createConversation({ client_id: selectedClient.id, phone: selectedPhone });
      setShowNewConv(false);
      setSelectedClient(null);
      setSelectedPhone("");
      setClientSearch("");
      await loadConversations();
      setSelectedConv(conv);
    } catch {
      // handle error
    }
  };

  const handleSearchClients = async (query, setter) => {
    if (query.length < 2) { setter([]); return; }
    try {
      const data = await searchClientes(query);
      setter(data.data || []);
    } catch { setter([]); }
  };

  const handleLinkClient = async (clientId) => {
    if (!selectedConv) return;
    setLinkLoading(true);
    try {
      const updated = await linkClient(selectedConv.id, { client_id: clientId });
      setSelectedConv(updated);
      setShowLinkModal(false);
      setLinkSearch("");
      setLinkResults([]);
      await loadConversations();
    } catch {
      // handle error
    } finally {
      setLinkLoading(false);
    }
  };

  const selectConversation = (conv) => {
    setSelectedConv(conv);
    setMessages([]);
  };

  return (
    <div className="flex h-[calc(100vh-7rem)] bg-white rounded-xl border overflow-hidden">
      {/* Left panel - Conversation list */}
      <div className={clsx(
        "flex flex-col border-r w-full md:w-80 md:min-w-[320px] shrink-0",
        selectedConv && "hidden md:flex"
      )}>
        {/* Header */}
        <div className="p-3 border-b space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-gray-800">Conversaciones</h2>
            <button
              onClick={() => setShowNewConv(true)}
              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500"
              title="Nueva conversación"
            >
              <Plus size={18} />
            </button>
          </div>
          <div className="relative">
            <Search size={16} className="absolute left-2.5 top-2.5 text-gray-400" />
            <input
              type="text"
              placeholder="Buscar..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              className="w-full pl-8 pr-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-300"
            />
          </div>
          {stats && (
            <div className="flex gap-3 text-xs text-gray-500">
              <span>{stats.active_conversations} activas</span>
              {stats.unlinked_conversations > 0 && (
                <span className="text-amber-600">{stats.unlinked_conversations} sin vincular</span>
              )}
              {stats.unread_total > 0 && (
                <span className="text-blue-600">{stats.unread_total} no leídos</span>
              )}
            </div>
          )}
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto">
          {loading && conversations.length === 0 ? (
            <div className="p-4 text-center text-sm text-gray-400">Cargando...</div>
          ) : conversations.length === 0 ? (
            <div className="p-4 text-center text-sm text-gray-400">Sin conversaciones</div>
          ) : (
            conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => selectConversation(conv)}
                className={clsx(
                  "w-full text-left px-3 py-3 border-b hover:bg-gray-50 transition-colors",
                  selectedConv?.id === conv.id && "bg-blue-50"
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      {!conv.client_id && (
                        <AlertTriangle size={13} className="text-amber-500 shrink-0" />
                      )}
                      <span className="text-sm font-medium text-gray-800 truncate">
                        {conv.client_name || conv.client_phone}
                      </span>
                    </div>
                    {conv.client_name && (
                      <div className="text-xs text-gray-400 truncate">{conv.client_phone}</div>
                    )}
                    <div className="text-xs text-gray-500 truncate mt-0.5">
                      {!conv.client_id && <span className="text-amber-600 font-medium">[Sin cliente] </span>}
                      {conv.last_message_preview || "Sin mensajes"}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-[10px] text-gray-400">{timeAgo(conv.last_message_at)}</div>
                    {conv.unread_count > 0 && (
                      <span className="inline-block mt-1 text-[10px] bg-blue-500 text-white rounded-full px-1.5 py-0.5 font-bold">
                        {conv.unread_count}
                      </span>
                    )}
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Right panel - Chat */}
      <div className={clsx(
        "flex-1 flex flex-col",
        !selectedConv && "hidden md:flex"
      )}>
        {!selectedConv ? (
          <div className="flex-1 flex items-center justify-center text-gray-400">
            <div className="text-center">
              <MessageCircle size={48} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">Selecciona una conversación</p>
            </div>
          </div>
        ) : (
          <>
            {/* Chat header */}
            <div className="px-4 py-3 border-b flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setSelectedConv(null)}
                  className="md:hidden p-1 rounded hover:bg-gray-100"
                >
                  <X size={18} />
                </button>
                <div>
                  <div className="flex items-center gap-2">
                    {!selectedConv.client_id && (
                      <AlertTriangle size={14} className="text-amber-500" />
                    )}
                    <span className="font-medium text-sm text-gray-800">
                      {selectedConv.client_name || selectedConv.client_phone}
                    </span>
                  </div>
                  <div className="text-xs text-gray-400 flex items-center gap-1">
                    <Phone size={10} />
                    {selectedConv.client_phone}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {!selectedConv.client_id && (
                  <button
                    onClick={() => setShowLinkModal(true)}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 rounded-lg hover:bg-amber-100"
                  >
                    <UserPlus size={13} />
                    Vincular cliente
                  </button>
                )}
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2 bg-gray-50">
              {msgLoading ? (
                <div className="text-center text-sm text-gray-400 py-8">Cargando mensajes...</div>
              ) : messages.length === 0 ? (
                <div className="text-center text-sm text-gray-400 py-8">Sin mensajes aún</div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={clsx(
                      "flex",
                      msg.direction === "OUTBOUND" ? "justify-end" : "justify-start"
                    )}
                  >
                    <div
                      className={clsx(
                        "max-w-[75%] rounded-xl px-3 py-2 text-sm",
                        msg.direction === "OUTBOUND"
                          ? "bg-blue-500 text-white"
                          : "bg-white border text-gray-800"
                      )}
                    >
                      {msg.sent_by_module && (
                        <div className={clsx(
                          "text-[10px] mb-1 flex items-center gap-1",
                          msg.direction === "OUTBOUND" ? "text-blue-200" : "text-gray-400"
                        )}>
                          <Bot size={10} />
                          via {msg.sent_by_module}
                        </div>
                      )}
                      {msg.message_type === "INTERACTIVE" && msg.direction === "OUTBOUND" && (
                        <div className={clsx(
                          "text-[10px] mb-1",
                          msg.direction === "OUTBOUND" ? "text-blue-200" : "text-gray-400"
                        )}>
                          [Menú interactivo]
                        </div>
                      )}
                      {msg.interactive_reply_title && msg.direction === "INBOUND" && (
                        <div className="text-[10px] text-gray-400 mb-1">
                          Seleccionó: {msg.interactive_reply_title}
                        </div>
                      )}
                      {msg.message_type === "IMAGE" && (
                        <AuthImage
                          src={`/api/comunicacion/messages/${msg.id}/media`}
                          alt={msg.media_filename || "imagen"}
                          className="max-w-[240px] rounded mb-1 cursor-pointer"
                          onClick={() => fetchMediaWithAuth(`/api/comunicacion/messages/${msg.id}/media`)}
                        />
                      )}
                      {msg.media_filename && msg.message_type !== "IMAGE" && (
                        <button
                          onClick={() => fetchMediaWithAuth(`/api/comunicacion/messages/${msg.id}/media`)}
                          className={clsx(
                            "text-xs mb-1 flex items-center gap-1 underline",
                            msg.direction === "OUTBOUND" ? "text-blue-200" : "text-gray-500"
                          )}
                        >
                          <Paperclip size={10} />
                          {msg.media_filename}
                        </button>
                      )}
                      {msg.content && <p className="whitespace-pre-wrap break-words">{msg.content}</p>}
                      <div className={clsx(
                        "flex items-center justify-end gap-1 mt-1 text-[10px]",
                        msg.direction === "OUTBOUND" ? "text-blue-200" : "text-gray-400"
                      )}>
                        <span>{new Date(msg.created_at).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" })}</span>
                        {msg.direction === "OUTBOUND" && <StatusIcon status={msg.wa_status} />}
                      </div>
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            <div className="px-4 py-3 border-t bg-white flex items-end gap-2">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={sendLoading}
                className="p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 disabled:opacity-50"
                title="Adjuntar archivo"
              >
                <Paperclip size={18} />
              </button>
              <textarea
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Escribe un mensaje..."
                rows={1}
                className="flex-1 resize-none px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-300 max-h-24"
              />
              <button
                onClick={handleSend}
                disabled={!newMessage.trim() || sendLoading}
                className="p-2 rounded-lg bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Send size={18} />
              </button>
            </div>
          </>
        )}
      </div>

      {/* New conversation modal */}
      {showNewConv && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-xl shadow-lg w-full max-w-md mx-4 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-800">Nueva conversación</h3>
              <button onClick={() => { setShowNewConv(false); setSelectedClient(null); setClientSearch(""); setClientResults([]); }} className="p-1 rounded hover:bg-gray-100">
                <X size={18} />
              </button>
            </div>

            <label className="text-sm text-gray-600 font-medium">Buscar cliente</label>
            <input
              type="text"
              value={clientSearch}
              onChange={(e) => { setClientSearch(e.target.value); handleSearchClients(e.target.value, setClientResults); }}
              placeholder="Nombre, CUIT, código..."
              className="w-full mt-1 px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-300"
            />
            {clientResults.length > 0 && !selectedClient && (
              <div className="mt-1 border rounded-lg max-h-40 overflow-y-auto">
                {clientResults.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => { setSelectedClient(c); setClientResults([]); }}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 border-b last:border-0"
                  >
                    <span className="font-medium">{c.legal_profile?.legal_name || `${c.human_profile?.first_name} ${c.human_profile?.last_name}`}</span>
                    <span className="text-xs text-gray-400 ml-2">{c.code}</span>
                  </button>
                ))}
              </div>
            )}

            {selectedClient && (
              <div className="mt-3">
                <div className="flex items-center justify-between bg-blue-50 rounded-lg px-3 py-2 mb-3">
                  <span className="text-sm font-medium text-blue-700">
                    {selectedClient.legal_profile?.legal_name || `${selectedClient.human_profile?.first_name} ${selectedClient.human_profile?.last_name}`}
                  </span>
                  <button onClick={() => { setSelectedClient(null); setSelectedPhone(""); }} className="text-blue-400 hover:text-blue-600">
                    <X size={14} />
                  </button>
                </div>

                <label className="text-sm text-gray-600 font-medium">Teléfono</label>
                <input
                  type="text"
                  value={selectedPhone}
                  onChange={(e) => setSelectedPhone(e.target.value)}
                  placeholder={selectedClient.phone || "+54 9 11 ..."}
                  className="w-full mt-1 px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-300"
                />
                {selectedClient.phone && (
                  <button
                    onClick={() => setSelectedPhone(selectedClient.phone)}
                    className="text-xs text-blue-600 hover:underline mt-1"
                  >
                    Usar teléfono principal: {selectedClient.phone}
                  </button>
                )}
              </div>
            )}

            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => { setShowNewConv(false); setSelectedClient(null); setClientSearch(""); }}
                className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg"
              >
                Cancelar
              </button>
              <button
                onClick={handleNewConversation}
                disabled={!selectedClient || !selectedPhone}
                className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                Iniciar chat
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Link client modal */}
      {showLinkModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-xl shadow-lg w-full max-w-md mx-4 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-800">Vincular a cliente</h3>
              <button onClick={() => { setShowLinkModal(false); setLinkSearch(""); setLinkResults([]); }} className="p-1 rounded hover:bg-gray-100">
                <X size={18} />
              </button>
            </div>

            <div className="text-xs text-gray-500 mb-3">
              Número: <span className="font-medium">{selectedConv?.client_phone}</span>
            </div>

            <label className="text-sm text-gray-600 font-medium">Buscar cliente</label>
            <input
              type="text"
              value={linkSearch}
              onChange={(e) => { setLinkSearch(e.target.value); handleSearchClients(e.target.value, setLinkResults); }}
              placeholder="Nombre, CUIT, código..."
              className="w-full mt-1 px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-300"
            />
            {linkResults.length > 0 && (
              <div className="mt-2 border rounded-lg max-h-48 overflow-y-auto">
                {linkResults.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => handleLinkClient(c.id)}
                    disabled={linkLoading}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 border-b last:border-0 disabled:opacity-50"
                  >
                    <span className="font-medium">
                      {c.legal_profile?.legal_name || `${c.human_profile?.first_name} ${c.human_profile?.last_name}`}
                    </span>
                    <span className="text-xs text-gray-400 ml-2">{c.code}</span>
                    {c.phone && <span className="text-xs text-gray-400 ml-2">{c.phone}</span>}
                  </button>
                ))}
              </div>
            )}

            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => { setShowLinkModal(false); setLinkSearch(""); setLinkResults([]); }}
                className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
