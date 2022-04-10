# frozen_string_literal: true

require 'bundler/inline'

gemfile do
  source 'https://rubygems.org'
  gem 'nokogiri'
end

def move_image_and_remove_paragraph(image)
  raise 'No image given' unless image

  to_remove = image.parent
  section = to_remove.parent
  section.add_child(image)
  to_remove.remove
end

@doc = File.open('index.html') { |f| Nokogiri::HTML(f) }

@doc.css('.stretch').each do |image|
  move_image_and_remove_paragraph(image)
end

File.open('index.html', 'w') { |f| f << @doc.to_html }
