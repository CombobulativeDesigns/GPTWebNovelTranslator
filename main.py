import json
import traceback
import yaml
import argparse
from src.gpt_wn_translator.api.openai_api import set_api_key
from src.gpt_wn_translator.encoders.json_encoder import JsonEncoder
from src.gpt_wn_translator.helpers.args_helper import parse_chapters
from src.gpt_wn_translator.helpers.file_helper import read_file, write_file, write_md_as_epub
from src.gpt_wn_translator.helpers.text_helper import make_printable, txt_to_md
from src.gpt_wn_translator.hooks.object_hook import generic_object_hook
from src.gpt_wn_translator.scrapers.soyetsu_scraper import process_novel
from src.gpt_wn_translator.translators.jp_to_en_translator import fix_linebreaks, translate_sub_chapter

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", help="Working directory path")
    parser.add_argument("novel_code", help="Novel code")
    parser.add_argument("-v", "--verbose", help="Verbose mode", action="store_true")
    parser.add_argument("-ss", "--skip-scraping", help="Skip scraping the novel", action="store_true")
    parser.add_argument("-st", "--skip-translating", help="Skip translating the novel", action="store_true")
    parser.add_argument("-se", "--skip-epub", help="Skip generating the epub", action="store_true")
    parser.add_argument("-c", "--chapters", help="The chapters to translate")
    args = parser.parse_args()

    if args.skip_scraping and args.skip_translating and args.skip_epub:
        print("Nothing to do")
        return
    
    if not args.skip_scraping and args.skip_translating and not args.skip_epub:
        print("Can't create epub without translating the novel after a fresh scraping.")
        return
    
    translation_targets = None
    if args.chapters:
        translation_targets = parse_chapters(args.chapters)
    novel_object_output_path = f"{args.directory}/{args.novel_code}/novel.json"
    novel_md_output_path = f"{args.directory}/{args.novel_code}/novel.md"
    novel_epub_output_path = f"{args.directory}/{args.novel_code}/novel.epub"

    config = yaml.safe_load(read_file("config/config.yaml", args.verbose))
    set_api_key(config["openai"]["api_key"])

    novel = None

    # ========================
    
    if not args.skip_scraping:
        try:
            novel = process_novel(args.novel_code, args.verbose)
            novel_printable = make_printable(json.dumps(novel, ensure_ascii=False, cls=JsonEncoder), args.verbose)
            write_file(novel_object_output_path, novel_printable, args.verbose)
        except Exception as e:
            print(e)
            return
        novel = json.loads(novel_printable, object_hook=generic_object_hook)
    else:
        try:
            novel = json.loads(read_file(novel_object_output_path, args.verbose), object_hook=generic_object_hook)
        except Exception as e:
            print(e)
            return
        
    # ========================
        
    if not args.skip_translating:
        # Iterate over chapters
        for target_chapter in translation_targets.keys():
            target_sub_chapters = translation_targets[target_chapter]
            target_chapter = int(target_chapter)
            # Check if the chapter exists in the novel object
            if target_chapter not in range(1, len(novel.chapters) + 1):
                print(f"Error: Chapter {target_chapter} not found in novel object")
                return
            
            chapter = novel.chapters[target_chapter - 1]
            # iterate over subchapters
            for target_sub_chapter in target_sub_chapters:
                target_sub_chapter = int(target_sub_chapter)
                if target_sub_chapter not in range(1, len(chapter.sub_chapters) + 1):
                    print(f"Error: SubChapter {target_sub_chapter} not found in novel object")
                    return
                
                try:
                    print(f"Translating chapter {target_chapter}, subchapter {target_sub_chapter}.") if args.verbose else None
                    translate_sub_chapter(novel, target_chapter, target_sub_chapter)
                except Exception as e:
                    traceback.print_exc()
                    print(f"Error: {e}")
                    return

        # Write the novel object to file
        try:
            novel_printable = make_printable(json.dumps(novel, ensure_ascii=False, cls=JsonEncoder), args.verbose)
            write_file(novel_object_output_path, novel_printable, args.verbose)
        except Exception as e:
            print(f"Error: {e}")
            return
        novel = json.loads(novel_printable, object_hook=generic_object_hook)

    # ========================

    if not args.skip_epub:
        sub_chapters_md = []
        # Iterate over chapters
        for target_chapter in translation_targets.keys():
            target_sub_chapters = translation_targets[target_chapter]
            target_chapter = int(target_chapter)
            # Check if the chapter exists in the novel object
            if target_chapter not in range(1, len(novel.chapters) + 1):
                print(f"Error: Chapter {target_chapter} not found in novel object")
                return
            
            if len(target_sub_chapters) > 0:
                chapter = novel.chapters[target_chapter - 1]
                # iterate over subchapters
                for target_sub_chapter in target_sub_chapters:
                    target_sub_chapter = int(target_sub_chapter)
                    if target_sub_chapter not in range(1, len(chapter.sub_chapters) + 1):
                        print(f"Error: SubChapter {target_sub_chapter} not found in novel object")
                        return
                    sub_chapter = chapter.sub_chapters[target_sub_chapter - 1]

                    print(f"Compiling chunks of chapter {target_chapter}, subchapter {target_sub_chapter}.") if args.verbose else None
                    sub_chapter_text = sub_chapter.name + "\n\n"

                    for chunk in sub_chapter.chunks:
                        print(f"Chunk {chunk} of {target_sub_chapter} of {target_chapter}... ", end="") if args.verbose else None
                        english = chunk.translation
                        japanese = chunk.context
                        fixed_english = fix_linebreaks(english, japanese)
                        sub_chapter_text += f"{fixed_english}\n\n"
                        print("Done") if args.verbose else None

                    sub_chapter_md = txt_to_md(sub_chapter_text)
                    sub_chapters_md.append(sub_chapter_md)
                    sub_chapter.translation = sub_chapter_text
            else:
                # If no subchapters are specified, translate all of them
                chapter = novel.chapters[target_chapter - 1]
                # iterate over subchapters
                for target_sub_chapter in range(1, len(chapter.sub_chapters) + 1):
                    sub_chapter = chapter.sub_chapters[target_sub_chapter - 1]

                    print(f"Compiling chunks of chapter {target_chapter}, subchapter {target_sub_chapter}.") if args.verbose else None
                    sub_chapter_text = sub_chapter.name + "\n\n"

                    for chunk in sub_chapter.chunks:
                        print(f"Chunk {chunk} of {target_sub_chapter} of {target_chapter}... ", end="") if args.verbose else None
                        english = chunk.translation
                        japanese = chunk.context
                        fixed_english = fix_linebreaks(english, japanese)
                        sub_chapter_text += f"{fixed_english}\n\n"
                        print("Done") if args.verbose else None

                    sub_chapter_md = txt_to_md(sub_chapter_text)
                    sub_chapters_md.append(sub_chapter_md)
                    sub_chapter.translation = sub_chapter_text

        # Write the novel object to file
        try:
            novel_printable = make_printable(json.dumps(novel, ensure_ascii=False, cls=JsonEncoder), args.verbose)
            write_file(novel_object_output_path, novel_printable, args.verbose)
        except Exception as e:
            print(f"Error: {e}")
            return

        write_md_as_epub(sub_chapters_md, novel_epub_output_path, args.verbose)
        write_file(novel_md_output_path, '\n\n'.join(sub_chapters_md), args.verbose)


if __name__ == "__main__":
    main()