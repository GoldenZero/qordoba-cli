package com.qordoba.cli

import com.opencsv.CSVWriter
import com.qordoba.cli.grammar.StringExtractorLexer
import com.qordoba.cli.grammar.StringExtractorLexer.{DOCSTRING, STRING_LITERAL}
import com.typesafe.scalalogging.slf4j.LazyLogging
import java.io.{BufferedWriter, File, FileWriter, StringWriter}
import org.antlr.v4.runtime.{CharStream, CharStreams, CommonTokenStream, Token}
import scala.collection.JavaConversions._
import scala.collection.mutable.ListBuffer

/**
  * Application that uses a precompiled ANTLR grammar to extract string literals from a given file
  */
object StringExtractorApp extends App with LazyLogging {
  /**
    * Main entry point for the StringExtractor application
    *
    * @param args
    */
  override def main(args: Array[String]) {

    // Parse command-line arguments
    val parser = new scopt.OptionParser[Config]("string-extractor") {
      head("string-extractor", "0.1")

      opt[String]('d', "input directory")
        .valueName("<directory>")
        .action( (x, c) => c.copy(directory = x) )
        .text("input directory is a required argument")

      opt[String]('i', "infile")
        .valueName("<file>")
        .action( (x, c) => c.copy(infile = x) )
        .text("infile is a required argument")

      opt[String]('o', "outfile")
        .required()
        .valueName("<file>")
        .action( (x, c) => c.copy(outfile = x) )
        .text("outfile is a required argument")

      opt[Unit]('v', "verbose").action( (_, c) =>
        c.copy(verbose = true) ).text("verbose is a flag")

      opt[Unit]('d', "debug").hidden().action( (_, c) =>
        c.copy(debug = true) ).text("this option is hidden in the usage text")

      help("help").text("prints this usage text")

      note("Application that uses a precompiled ANTLR grammar to extract string literals from a given file or directory")

    }

    parser.parse(args, Config()) match {
      case Some(config) =>
        // Either input file or input directory must be provided
        val infileName: String = if (config.directory.length > 0) {
          config.directory
        } else {
          config.infile
        }
        new StringExtractorApp(infileName, config.outfile).extractStrings()

      case None =>
        logger.error("Bad config")
    }
  }
}

class StringExtractorApp(infileName: String, outfileName: String) extends LazyLogging {

  /**
    * Main driver for the class. Calls all relevant methods to extract string literals
    * and write them to the given output file in CSV format.
    */
  def extractStrings() = {
    try {
      val infile = new File(infileName)
      val stringLiterals: List[StringLiteral] = {
        // Gather a list of all files
        val files: List[File] = this.getFilesRecursive(infile).toList

        // Fetch tokens, then string literals for each file & concatenate into a single list
        files.map { f =>
            val tokens = this.getTokens(f.getPath)
            // Inspect each token for something interesting
            this.findStringLiterals(f.getPath, tokens)
          }
          .foldLeft(List[StringLiteral]())(_ ++ _)
      }

      // Send our treasures to a file
      this.generateCsv(stringLiterals, outfileName)

    } catch {
      case e: Exception => {
        logger.error(s"Unable to parse ${infileName}: ${e}")
        throw e
      }
    }
  }

  /**
    * Compiles a list of files in a given directory, recursively. Also handles a non-directory argument.
    * List includes only files, not directories.
    *
    * @param dir
    * @return
    */
  def getFilesRecursive(dir: File): Array[File] = {
    if (dir.exists()) {
      if (dir.isDirectory) {
        val these = dir.listFiles
        these.filter(!_.isDirectory) ++ these.filter(_.isDirectory).flatMap(getFilesRecursive)
      } else {
        Array[File](dir)
      }
    } else {
      Array[File]()
    }
  }

  /**
    * Performs lexical analysis (tokenization) using ANTLR4-generated classes.
    * The underlying grammar is designed to differentiate string literals from
    * all other characters.
    *
    * @return iterator of tokens
    */
  def getTokens(infileName: String): Iterator[Token] = {
    try {
      val input: CharStream = CharStreams.fromFileName(infileName)
      val lexer: StringExtractorLexer = new StringExtractorLexer(input)
      val tokenStream: CommonTokenStream = new CommonTokenStream(lexer)

      // Activate the lexer
      tokenStream.fill()

      // Retrieve the token iterator
      tokenStream.getTokens().iterator()
    } catch {
      case e: Exception => {
        logger.error(s"Unable to generate tokens for ${infileName}: ${e}")
        throw e
      }
    }
  }

  /**
    * Extracts relevant tokens (i.e. StringLiterals) from a list of arbitrary tokens.
    * Stores related information about where the token was found.
    *
    * @param infileName
    * @param tokens
    * @return list of StringLiterals
    */
  def findStringLiterals(infileName: String, tokens: Iterator[Token]): List[StringLiteral] = {
    // A place to store everything that should go in the output file
    val allStringLiterals: ListBuffer[StringLiteral] = scala.collection.mutable.ListBuffer.empty[StringLiteral]

    try {
      // Inspect each token for something interesting
      while (tokens.hasNext()) {
        val token: Token = tokens.next()

        // Only process string literals & docstrings (do we really want to include docstrings?)
        if (token.getType() == STRING_LITERAL || token.getType() == DOCSTRING) {
          // TODO: Support CR+LF for endLineNumber
          val stringLiteral: StringLiteral = new StringLiteral(
            filename = infileName,
            startLineNumber = token.getLine(),
            startCharIdx = token.getCharPositionInLine(),
            endLineNumber = token.getLine() + token.getText().count(_ == '\u000A'), // startLineNumber + newline count
            endCharIdx = token.getCharPositionInLine() + token.getText().size - 1,  // 0-based index, inclusive
            text = token.getText()
          )
          allStringLiterals += stringLiteral
        }
      }
    } catch {
      case e: Exception => {
        logger.error(s"Unable to filter tokens for ${infileName}: ${e}")
        throw e
      }
    }

    allStringLiterals.toList
  }

  /**
    * Generates a CSV file containing a single record for each given StringLiteral.
    * Generated file is default CSV format (comma-delimited with double quotes for string literals).
    *
    * @param stringLiterals
    * @param outfileName
    */
  def generateCsv(stringLiterals: List[StringLiteral], outfileName: String) = {
    val writer = new StringWriter()
    val csvWriter = new CSVWriter(writer)

    // Convert to a format that OpenCSV can do something with
    val toWrite: List[Array[String]] = stringLiterals.map(stringLiteral => stringLiteral.toStringArray())

    csvWriter.writeAll(toWrite, false)
    csvWriter.close()

    val outfile = new File(outfileName)
    val bw = new BufferedWriter(new FileWriter(outfile))
    bw.write(writer.toString())
    bw.close()

    logger.debug(s"String literals written to ${outfileName}")
  }

}

