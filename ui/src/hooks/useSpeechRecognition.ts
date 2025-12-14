import { useState, useEffect, useRef, useCallback } from 'react';

interface SpeechRecognitionEvent extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: (event: SpeechRecognitionEvent) => void;
  onerror: (event: Event) => void;
  onend: () => void;
  onstart: () => void;
}

interface WindowWithSpeech extends Window {
  SpeechRecognition?: new () => SpeechRecognition;
  webkitSpeechRecognition?: new () => SpeechRecognition;
}

export interface SpeechChunk {
  text: string;
  is_final: boolean;
  result_index?: number;
}

export const useSpeechRecognition = (
  onChunk: (chunk: SpeechChunk) => void,
  enabled: boolean = false
) => {
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const finalTranscriptRef = useRef<string>('');
  const lastProcessedIndexRef = useRef<number>(0);
  const lastInterimTextRef = useRef<string>('');

  useEffect(() => {
    const windowWithSpeech = window as WindowWithSpeech;
    const SpeechRecognition = windowWithSpeech.SpeechRecognition || windowWithSpeech.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setError('Speech recognition is not supported in this browser. Please use Chrome or Edge.');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      setIsListening(true);
      setError(null);
      finalTranscriptRef.current = '';
      lastProcessedIndexRef.current = 0;
      lastInterimTextRef.current = '';
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let newFinalTranscript = '';
      let currentInterimTranscript = '';

      // Build the full transcript from all results
      // Separate final and interim results
      for (let i = 0; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          // Only process NEW final results (from lastProcessedIndexRef onwards)
          if (i >= lastProcessedIndexRef.current) {
            newFinalTranscript += transcript + ' ';
          }
        } else {
          // Build current interim transcript (all non-final results)
          currentInterimTranscript += transcript;
        }
      }

      // Send final chunk if we have new final text
      if (newFinalTranscript.trim()) {
        finalTranscriptRef.current += newFinalTranscript;
        onChunk({
          text: newFinalTranscript.trim(),
          is_final: true,
          result_index: event.resultIndex,
        });
        // Update last processed index to after the final results
        // Find the last final result index
        for (let i = event.results.length - 1; i >= 0; i--) {
          if (event.results[i].isFinal) {
            lastProcessedIndexRef.current = i + 1;
            break;
          }
        }
      }

      // Send interim chunk - send the full current interim text
      // The backend will clear previous interim chunks before adding this one
      if (currentInterimTranscript && currentInterimTranscript !== lastInterimTextRef.current) {
        onChunk({
          text: currentInterimTranscript,
          is_final: false,
          result_index: event.resultIndex,
        });
        lastInterimTextRef.current = currentInterimTranscript;
      } else if (!currentInterimTranscript && lastInterimTextRef.current) {
        // Clear interim text if there's none (all results are final)
        lastInterimTextRef.current = '';
      }
    };

    recognition.onerror = (event: any) => {
      const errorMessage = event.error || 'Unknown error occurred';
      setError(`Speech recognition error: ${errorMessage}`);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
        recognitionRef.current = null;
      }
    };
  }, [onChunk]);

  const start = useCallback(() => {
    if (recognitionRef.current && !isListening) {
      try {
        recognitionRef.current.start();
      } catch (err) {
        // Ignore if already started
        console.log('Recognition already started or starting');
      }
    }
  }, [isListening]);

  const stop = useCallback(() => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
    }
  }, [isListening]);

  useEffect(() => {
    if (enabled) {
      start();
    } else {
      stop();
    }
  }, [enabled, start, stop]);

  return {
    isListening,
    error,
    start,
    stop,
    isSupported: recognitionRef.current !== null,
  };
};

