@echo off
REM ===========================================================================
REM  Lancement du serveur Ollama pour l'agent d'accessibilite.
REM
REM  Le code Python n'a PAS a connaitre le materiel : il parle a l'API locale
REM  http://localhost:11434. Ce script choisit simplement quel moteur demarrer.
REM
REM  Priorite : 1) Ollama accelere Intel (IPEX-LLM)  2) Ollama par defaut
REM  (Ollama par defaut detecte tout seul une carte NVIDIA / CUDA.)
REM
REM  >>> A ADAPTER : mettez le chemin de VOTRE ollama Intel dans INTEL_OLLAMA.
REM ===========================================================================

REM -- Partage du meme dossier de modeles pour eviter tout re-telechargement --
set OLLAMA_MODELS=%USERPROFILE%\.ollama\models

REM -- Chemin de l'executable Ollama accelere Intel (portable zip IPEX-LLM) ----
set INTEL_OLLAMA=C:\ollama-intel\ollama.exe

REM -- Variables utiles a la version Intel (sans effet sur l'autre) ------------
set no_proxy=localhost,127.0.0.1
set ZES_ENABLE_SYSMAN=1
set OLLAMA_NUM_GPU=999

if exist "%INTEL_OLLAMA%" (
    echo [start-ollama] Version Intel detectee : lancement accelere GPU Intel...
    "%INTEL_OLLAMA%" serve
) else (
    echo [start-ollama] Version Intel absente : bascule sur Ollama par defaut.
    echo                (NVIDIA/CUDA sera utilise automatiquement s'il est present.)
    ollama serve
)
