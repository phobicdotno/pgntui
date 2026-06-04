# Stub formula for phobicdotno/homebrew-tap
# Install: brew install phobicdotno/tap/pgntui
class Pgntui < Formula
  desc "Cross-platform TUI for NMEA 2000 with canboat decoding"
  homepage "https://github.com/phobicdotno/pgntui"
  url "https://files.pythonhosted.org/packages/source/p/pgntui/pgntui-0.3.0.tar.gz"
  sha256 "REPLACE_ON_RELEASE"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "pgntui", shell_output("#{bin}/pgntui --help", 2)
  end
end
