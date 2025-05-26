import copy
import os
import tempfile
import sys #windows인지 운영체제 확인하고 싶어서, windows 환경일 경우만 개선 코드 적용
import time #time.sleep 사용을 위해 모듈이 필요 

from dynaconf import Dynaconf
from starlette_context import context

from pr_agent.config_loader import get_settings
from pr_agent.git_providers import get_git_provider_with_context
from pr_agent.log import get_logger

# line 16~66 origin code
# def apply_repo_settings(pr_url):
#     os.environ["AUTO_CAST_FOR_DYNACONF"] = "false"
#     git_provider = get_git_provider_with_context(pr_url)
#     if get_settings().config.use_repo_settings_file:
#         repo_settings_file = None
#         try:
#             try:
#                 repo_settings = context.get("repo_settings", None)
#             except Exception:
#                 repo_settings = None
#                 pass
#             if repo_settings is None:  # None is different from "", which is a valid value
#                 repo_settings = git_provider.get_repo_settings()
#                 try:
#                     context["repo_settings"] = repo_settings
#                 except Exception:
#                     pass

#             error_local = None
#             if repo_settings:
#                 repo_settings_file = None
#                 category = 'local'
#                 try:
#                     fd, repo_settings_file = tempfile.mkstemp(suffix='.toml')
#                     os.write(fd, repo_settings)
#                     new_settings = Dynaconf(settings_files=[repo_settings_file])
#                     for section, contents in new_settings.as_dict().items():
#                         section_dict = copy.deepcopy(get_settings().as_dict().get(section, {}))
#                         for key, value in contents.items():
#                             section_dict[key] = value
#                         get_settings().unset(section)
#                         get_settings().set(section, section_dict, merge=False)
#                     get_logger().info(f"Applying repo settings:\n{new_settings.as_dict()}")
#                 except Exception as e:
#                     get_logger().warning(f"Failed to apply repo {category} settings, error: {str(e)}")
#                     error_local = {'error': str(e), 'settings': repo_settings, 'category': category}

#                 if error_local:
#                     handle_configurations_errors([error_local], git_provider)
#         except Exception as e:
#             get_logger().exception("Failed to apply repo settings", e)
#         finally:
#             if repo_settings_file:
#                 try:
#                     os.remove(repo_settings_file)
#                 except Exception as e:
#                     get_logger().error(f"Failed to remove temporary settings file {repo_settings_file}", e)

#     # enable switching models with a short definition
#     if get_settings().config.model.lower() == 'claude-3-5-sonnet':
#         set_claude_model()

# --- 이 함수 전체를 복사하여 기존 apply_repo_settings 함수와 교체하세요 ---
def apply_repo_settings(pr_url):
    os.environ["AUTO_CAST_FOR_DYNACONF"] = "false"
    git_provider = get_git_provider_with_context(pr_url)
    repo_settings_file = None # finally 절에서 사용하기 위해 try 블록 외부에서 초기화
    fd = -1                   # 파일 디스크립터 초기화

    if get_settings().config.use_repo_settings_file:
        try:
            # --- 리포지토리 설정 가져오기 (기존 로직과 동일) ---
            try:
                repo_settings = context.get("repo_settings", None)
            except Exception:
                repo_settings = None
                pass
            if repo_settings is None:
                repo_settings = git_provider.get_repo_settings()
                try:
                    context["repo_settings"] = repo_settings
                except Exception:
                    pass

            error_local = None
            if repo_settings:
                category = 'local'
                try:
                    # --- 임시 파일 생성, 쓰기, 그리고 닫기 ---
                    # 1. 임시 파일 생성하고 파일 디스크립터(fd)와 경로(repo_settings_file) 얻기
                    fd, repo_settings_file = tempfile.mkstemp(suffix='.toml')
                    # 2. 파일에 설정 내용 쓰기
                    os.write(fd, repo_settings)
                    # 3. ★ 개선점 1: 파일 디스크립터 명시적으로 닫기 (파일 잠금 해제 도움) ★
                    os.close(fd)
                    fd = -1 # 닫은 후 초기화

                    # --- 임시 파일에서 설정 로드 (기존 로직과 동일) ---
                    new_settings = Dynaconf(settings_files=[repo_settings_file])
                    for section, contents in new_settings.as_dict().items():
                        section_dict = copy.deepcopy(get_settings().as_dict().get(section, {}))
                        for key, value in contents.items():
                            section_dict[key] = value
                        get_settings().unset(section)
                        get_settings().set(section, section_dict, merge=False)
                    get_logger().info(f"Applying repo settings:\n{new_settings.as_dict()}")

                except Exception as e:
                    # --- 설정 적용 중 오류 처리 (기존 로직과 동일) ---
                    get_logger().warning(f"Failed to apply repo {category} settings, error: {str(e)}")
                    error_local = {'error': str(e), 'settings': repo_settings, 'category': category}
                    # 쓰기/Dynaconf 실패 시에도 fd 닫기 시도
                    if fd != -1:
                        try:
                            os.close(fd)
                        except OSError:
                            pass # 이미 닫혔거나 유효하지 않으면 무시

            if error_local:
                handle_configurations_errors([error_local], git_provider)

        except Exception as e:
            get_logger().exception("Failed to apply repo settings", e)
        finally:
            # --- 임시 파일 정리 (finally 블록은 항상 실행됨) ---
            if repo_settings_file: # 임시 파일이 생성된 경우에만 실행
                # ★ 개선점 2: 운영체제 확인 ★
                if sys.platform == 'win32': # 현재 운영체제가 Windows 인 경우
                    # ★ 개선점 3 & 4: Windows 에서만 재시도 로직 및 로그 레벨 변경 적용 ★
                    attempts = 2  # 최대 2번 시도
                    delay = 0.1 # 시도 간 0.1초 대기
                    for i in range(attempts):
                        try:
                            os.remove(repo_settings_file) # 파일 삭제 시도
                            get_logger().debug(f"Successfully removed temporary settings file {repo_settings_file}")
                            repo_settings_file = None # 성공 시 경로 변수 초기화 (더 이상 삭제 시도 안 함)
                            break # 성공했으니 반복 종료
                        except Exception as e:
                            if i < attempts - 1: # 마지막 시도가 아니라면
                                get_logger().warning(f"Attempt {i+1} failed to remove {repo_settings_file} on Windows, retrying in {delay}s...")
                                time.sleep(delay) # 잠시 대기
                            else: # 마지막 시도에도 실패하면 ERROR 대신 WARNING 로그 남기기
                                get_logger().warning(f"Failed to remove temporary settings file {repo_settings_file} on Windows after {attempts} attempts", exc_info=True)
                                # 실패해도 repo_settings_file 변수는 유지 (수동 삭제 위해)
                else:
                    # Windows가 아닌 다른 OS (macOS, Linux 등)의 경우
                    # 기존 방식대로 한 번만 삭제 시도하고 실패 시 ERROR 로그 남기기
                    try:
                        os.remove(repo_settings_file)
                        get_logger().debug(f"Successfully removed temporary settings file {repo_settings_file}")
                        repo_settings_file = None
                    except Exception as e:
                        get_logger().error(f"Failed to remove temporary settings file {repo_settings_file} on {sys.platform}", exc_info=True)

    # --- 나머지 함수 로직 (기존과 동일) ---
    if get_settings().config.model.lower() == 'claude-3-5-sonnet':
        set_claude_model()
#

def handle_configurations_errors(config_errors, git_provider):
    try:
        if not any(config_errors):
            return

        for err in config_errors:
            if err:
                configuration_file_content = err['settings'].decode()
                err_message = err['error']
                config_type = err['category']
                header = f"❌ **PR-Agent failed to apply '{config_type}' repo settings**"
                body = f"{header}\n\nThe configuration file needs to be a valid [TOML](https://qodo-merge-docs.qodo.ai/usage-guide/configuration_options/), please fix it.\n\n"
                body += f"___\n\n**Error message:**\n`{err_message}`\n\n"
                if git_provider.is_supported("gfm_markdown"):
                    body += f"\n\n<details><summary>Configuration content:</summary>\n\n```toml\n{configuration_file_content}\n```\n\n</details>"
                else:
                    body += f"\n\n**Configuration content:**\n\n```toml\n{configuration_file_content}\n```\n\n"
                get_logger().warning(f"Sending a 'configuration error' comment to the PR", artifact={'body': body})
                # git_provider.publish_comment(body)
                if hasattr(git_provider, 'publish_persistent_comment'):
                    git_provider.publish_persistent_comment(body,
                                                            initial_header=header,
                                                            update_header=False,
                                                            final_update_message=False)
                else:
                    git_provider.publish_comment(body)
    except Exception as e:
        get_logger().exception(f"Failed to handle configurations errors", e)


def set_claude_model():
    """
    set the claude-sonnet-3.5 model easily (even by users), just by stating: --config.model='claude-3-5-sonnet'
    """
    model_claude = "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0"
    get_settings().set('config.model', model_claude)
    get_settings().set('config.model_weak', model_claude)
    get_settings().set('config.fallback_models', [model_claude])
