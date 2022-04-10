pandoc -f markdown slides.md -t revealjs -o index.html -V mouseWheel=true -V history=true -V controls=false -V slideNumber="'c/t'" --standalone
ruby fix_images.rb
PAUSE